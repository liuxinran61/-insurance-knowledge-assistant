import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.schemas.rag import (
    DocumentDetailResponse,
    DocumentResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    SourceReference,
)
from app.models.document import DocumentChunk
from app.services.llm_observability_service import (
    create_llm_call_log,
    elapsed_ms,
    extract_usage,
    start_timer,
)
from app.services.llm_service import get_llm_client
from app.services.rag_service import RAGService, append_session_message, load_session_history
from app.utils.file_parser import get_supported_extensions, parse_file
from app.worker.tasks import process_document_task
from app.agents.knowledge_agent import KnowledgeAgent

router = APIRouter()

SUPPORTED_EXTENSIONS = get_supported_extensions()
SUPPORTED_EXT_TEXT = ", ".join(SUPPORTED_EXTENSIONS)


def build_source_references(chunks: list[DocumentChunk]) -> list[SourceReference]:
    """将向量检索片段转换为前端可展示的资料引用。"""
    return [
        SourceReference(
            document_id=chunk.document.id,
            chunk_index=chunk.chunk_index,
            filename=chunk.document.filename,
            business_line=chunk.document.business_line,
            product=chunk.document.product,
            knowledge_version=chunk.document.knowledge_version,
            effective_at=chunk.document.effective_at,
            folder_path=chunk.document.folder_path,
            excerpt=chunk.content[:300].strip(),
        )
        for chunk in chunks
    ]


def build_context_text(chunks: list[DocumentChunk]) -> str:
    """在提示词中保留来源标签，让模型知道每段资料来自哪里。"""
    context_texts = []
    for index, chunk in enumerate(chunks, start=1):
        document = chunk.document
        version = document.knowledge_version or "未标注版本"
        effective_at = (
            document.effective_at.date().isoformat()
            if document.effective_at
            else "未标注生效日"
        )
        context_texts.append(
            f"[相关资料 {index} | 文件: {document.filename} | 版本: {version} | 生效: {effective_at}]\n"
            f"{chunk.content}"
        )
    return "\n\n".join(context_texts)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="上传文档并异步构建知识库（支持 .txt / .md / .pdf）",
    tags=["RAG"],
)
async def upload_document(
    file: UploadFile = File(...),
    business_line: Optional[str] = Form(None),
    product: Optional[str] = Form(None),
    knowledge_version: Optional[str] = Form(None),
    effective_at: Optional[datetime] = Form(None),
    folder_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    上传文档（支持 .txt / .md / .pdf），先解析并保存纯文本内容，再异步执行切分和向量化。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    if len(file.filename) > 255:
        raise HTTPException(status_code=400, detail="Filename too long (max 255 characters).")

    name_lower = file.filename.lower()
    if not any(name_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {SUPPORTED_EXT_TEXT}",
        )

    raw_bytes = await file.read()

    try:
        parsed = parse_file(file.filename, raw_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    if not parsed.plain_text.strip():
        raise HTTPException(status_code=400, detail="File contains no extractable text.")

    rag_service = RAGService(db)
    doc = None
    try:
        doc = rag_service.create_document_record(
            filename=file.filename,
            file_type=parsed.file_type,
            content=parsed.plain_text,
            owner_id=current_user.id,
            business_line=business_line,
            product=product,
            knowledge_version=knowledge_version,
            effective_at=effective_at,
            folder_path=folder_path,
        )
        task = process_document_task.delay(doc.id)
        doc = rag_service.attach_processing_task(
            document_id=doc.id,
            owner_id=current_user.id,
            task_id=task.id,
        )
        return doc
    except Exception as e:
        if doc is not None:
            rag_service.mark_document_failed(document_id=doc.id, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@router.get(
    "/documents",
    response_model=list[DocumentResponse],
    summary="查看当前用户的知识库文档",
    tags=["RAG"],
)
async def list_documents(
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user)
):
    rag_service = RAGService(db)
    return rag_service.list_documents_for_user(owner_id=current_user.id)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
    summary="查看文档详情与已解析文本",
    tags=["RAG"],
)
async def get_document(
    document_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)
):
    rag_service = RAGService(db)
    document = rag_service.get_document_for_user(document_id=document_id, owner_id=current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@router.delete(
    "/documents/{document_id}",
    summary="删除指定文档（含已处理的向量块）",
    tags=["RAG"],
)
async def delete_document(
    document_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)
):
    rag_service = RAGService(db)
    document = rag_service.delete_document(document_id=document_id, owner_id=current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return JSONResponse(
        content={"message": f"文档 '{document.filename}' 已删除", "document_id": document.id}
    )


@router.post(
    "/query", response_model=RAGQueryResponse, summary="基于知识库检索并回答", tags=["RAG"]
)
async def query_knowledge_base(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    1. 接收用户 Query 并计算向量
    2. 使用 pgvector 检索最相似的文档块 (top_k)
    3. 组装 prompt，调用 LLM (Qwen2.5) 生成答案
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    rag_service = RAGService(db)
    started_at = start_timer()
    try:
        history = None
        if request.session_id:
            history = await load_session_history(
                current_user.id,
                request.session_id,
            )

        agent_result = await KnowledgeAgent(rag_service).run(
            query=request.query,
            owner_id=current_user.id,
            history=history,
            business_line=request.business_line,
            product=request.product,
            as_of=request.as_of,
            document_id=request.document_id,
            folder_path=request.folder_path,
        )

        sources = [
            SourceReference(
                document_id=source["document_id"],
                chunk_index=source["chunk_index"],
                filename=source["filename"],
                folder_path=source.get("folder_path"),
                product=source.get("product"),
                knowledge_version=source.get("knowledge_version"),
                effective_at=source.get("effective_at"),
                excerpt=source["content"][:300].strip(),
            )
            for source in agent_result.sources
        ]

        if request.session_id:
            await append_session_message(
                current_user.id,
                request.session_id,
                "user",
                request.query,
            )
            await append_session_message(
                current_user.id,
                request.session_id,
                "assistant",
                agent_result.answer,
            )

        create_llm_call_log(
            db,
            user_id=current_user.id,
            endpoint="/api/v1/rag/query",
            prompt=request.query,
            response=agent_result.answer,
            tool_calls=(
                json.dumps(agent_result.tool_calls, ensure_ascii=False)
                if agent_result.tool_calls
                else None
            ),
            prompt_tokens=agent_result.prompt_tokens,
            completion_tokens=agent_result.completion_tokens,
            total_tokens=agent_result.total_tokens,
            latency_ms=elapsed_ms(started_at),
            status="success",
        )

        return RAGQueryResponse(
            query=request.query,
            answer=agent_result.answer,
            source_chunks=[
                source["content"]
                for source in agent_result.sources
            ],
            sources=sources,
        )

    except Exception as e:
        create_llm_call_log(
            db,
            user_id=current_user.id,
            endpoint="/api/v1/rag/query",
            prompt=request.query,
            response=None,
            tool_calls=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=elapsed_ms(started_at),
            status="failed",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")


@router.post("/query/stream", summary="基于知识库检索并流式回答 (SSE)", tags=["RAG"])
async def query_knowledge_base_stream(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    rag_service = RAGService(db)
    chunks = await rag_service.retrieve_relevant_chunks(
        query=request.query,
        owner_id=current_user.id,
        top_k=request.top_k,
        business_line=request.business_line,
        product=request.product,
        as_of=request.as_of,
        document_id=request.document_id,
        folder_path=request.folder_path,
    )

    if not chunks:

        async def _empty():
            data = json.dumps(
                {
                    "content": "知识库中暂无已处理完成的相关文档，请先上传文档并等待处理完成。",
                    "source_chunks": [],
                    "sources": [],
                },
                ensure_ascii=False,
            )
            yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_empty(), media_type="text/event-stream")

    context_str = build_context_text(chunks)
    system_prompt = (
        "你是一个专业的问答助手。请基于以下提供的参考资料，准确回答用户的问题。\n"
        "如果你不知道答案，或者参考资料中没有相关信息，请直接说明，不要编造。\n\n"
        f"=== 参考资料 ===\n{context_str}\n=== 结束 ==="
    )

    source_chunk_contents = [chunk.content for chunk in chunks]
    sources = build_source_references(chunks)

    async def _stream():
        llm_info = get_llm_client(current_user)
        full_response = ""

        stream_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.query},
        ]

        if request.session_id:
            session_history = await load_session_history(current_user.id, request.session_id)
            await append_session_message(current_user.id, request.session_id, "user", request.query)
            stream_messages = (
                [{"role": "system", "content": system_prompt}]
                + session_history
                + [{"role": "user", "content": request.query}]
            )

        try:
            response = await llm_info.client.chat.completions.create(
                model=llm_info.model_name,
                messages=stream_messages,
                temperature=0.1,
                stream=True,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    data = json.dumps({"content": content}, ensure_ascii=False)
                    yield f"data: {data}\n\n"

            if request.session_id and full_response:
                await append_session_message(
                    current_user.id, request.session_id, "assistant", full_response
                )

            data = json.dumps(
                {
                    "source_chunks": source_chunk_contents,
                    "sources": [source.model_dump(mode="json") for source in sources],
                },
                ensure_ascii=False,
            )
            yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")
