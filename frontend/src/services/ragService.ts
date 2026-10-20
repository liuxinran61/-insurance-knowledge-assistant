import api from './api'
import type { Document, DocumentDetail, KnowledgeSource } from '@/types'

export interface DocumentMetadata {
  businessLine?: string
  product?: string
  knowledgeVersion?: string
  effectiveAt?: string
  folderPath?: string
}

export interface KnowledgeQueryFilters {
  businessLine?: string
  product?: string
  asOf?: string
  documentId?: number
  folderPath?: string
}

export type SourceReference = KnowledgeSource

export interface KnowledgeQueryResult {
  answer: string
  source_chunks: string[]
  sources: SourceReference[]
}

function buildQueryPayload(
  query: string,
  topK: number,
  filters: KnowledgeQueryFilters,
  sessionId?: string,
): {
  query: string
  top_k: number
  business_line?: string
  product?: string
  as_of?: string
  document_id?: number
  folder_path?: string
  session_id?: string
} {
  return {
    query,
    top_k: topK,
    business_line: filters.businessLine || undefined,
    product: filters.product || undefined,
    as_of: filters.asOf || undefined,
    document_id: filters.documentId || undefined,
    folder_path: filters.folderPath || undefined,
    session_id: sessionId || undefined,
  }
}

export async function listDocuments(): Promise<Document[]> {
  const response = await api.get<Document[]>('/rag/documents')
  return response.data
}

export async function getDocument(documentId: number): Promise<DocumentDetail> {
  const response = await api.get<DocumentDetail>(`/rag/documents/${documentId}`)
  return response.data
}

export async function uploadDocument(
  file: File,
  metadata: DocumentMetadata = {},
): Promise<Document> {
  const formData = new FormData()
  formData.append('file', file)
  if (metadata.businessLine) {
    formData.append('business_line', metadata.businessLine)
  }
  if (metadata.product) {
    formData.append('product', metadata.product)
  }
  if (metadata.knowledgeVersion) {
    formData.append('knowledge_version', metadata.knowledgeVersion)
  }
  if (metadata.effectiveAt) {
    formData.append('effective_at', metadata.effectiveAt)
  }
  if (metadata.folderPath) {
    formData.append('folder_path', metadata.folderPath)
  }
  const response = await api.post<Document>('/rag/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function deleteDocument(documentId: number): Promise<void> {
  await api.delete(`/rag/documents/${documentId}`)
}

export async function queryKnowledgeBase(
  query: string,
  topK = 3,
  filters: KnowledgeQueryFilters = {},
  sessionId?: string,
): Promise<KnowledgeQueryResult> {
  const response = await api.post<KnowledgeQueryResult>(
    '/rag/query',
    buildQueryPayload(query, topK, filters, sessionId),
  )
  return response.data
}

export async function* streamQueryKnowledgeBase(
  query: string,
  topK = 3,
  filters: KnowledgeQueryFilters = {},
  sessionId?: string,
): AsyncGenerator<{
  content?: string
  source_chunks?: string[]
  sources?: SourceReference[]
  error?: string
}> {
  const token = localStorage.getItem('agent_token')
  const baseUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  const url = `${baseUrl}/rag/query/stream`

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(buildQueryPayload(query, topK, filters, sessionId)),
  })

  if (!response.ok) {
    let errorMsg = '查询失败'
    try {
      const err = await response.json()
      errorMsg = err.detail || errorMsg
    } catch {}
    yield { error: errorMsg }
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    yield { error: '无法读取响应流' }
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue

        const data = trimmed.slice(6)
        if (data === '[DONE]') return

        try {
          const parsed = JSON.parse(data)
          yield parsed
        } catch {}
      }
    }
  } finally {
    reader.releaseLock()
  }
}
