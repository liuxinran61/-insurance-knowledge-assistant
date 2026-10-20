import { useState, useEffect, useRef, type ChangeEvent } from 'react'
import type { Document, DocumentDetail } from '@/types'
import {
  deleteDocument,
  getDocument,
  listDocuments,
  uploadDocument,
} from '@/services/ragService'
import { IconFile, IconUpload, IconTrash, IconRefresh, IconX } from '@/components/ui/Icons'
import { statusLabels, statusColors } from '@/components/knowledge/constants'

export default function KnowledgePanel() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [metadata, setMetadata] = useState({
    businessLine: '',
    product: '',
    knowledgeVersion: '',
    effectiveAt: '',
    folderPath: '',
  })
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetail | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  async function loadDocs() {
    setError('')
    try {
      const data = await listDocuments()
      setDocuments(data)
    } catch {
      setError('加载文档失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocs()
  }, [])

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    setUploading(true)
    try {
      await uploadDocument(file, {
        businessLine: metadata.businessLine || undefined,
        product: metadata.product || undefined,
        knowledgeVersion: metadata.knowledgeVersion || undefined,
        effectiveAt: metadata.effectiveAt
          ? `${metadata.effectiveAt}T00:00:00+08:00`
          : undefined,
        folderPath: metadata.folderPath.trim() || undefined,
      })
      await loadDocs()
      setMetadata({
        businessLine: '',
        product: '',
        knowledgeVersion: '',
        effectiveAt: '',
        folderPath: '',
      })
    } catch {
      setError('上传失败，请重试')
    }
    if (fileRef.current) fileRef.current.value = ''
    setUploading(false)
  }

  async function handleDelete(id: number) {
    setError('')
    try {
      await deleteDocument(id)
      await loadDocs()
    } catch {
      setError('删除失败，请重试')
    }
  }

  async function handlePreview(id: number) {
    setError('')
    setPreviewLoading(true)
    try {
      setSelectedDocument(await getDocument(id))
    } catch {
      setError('加载文档预览失败')
    } finally {
      setPreviewLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3 rounded-xl border border-[var(--border-primary)] p-3">
        <div className="grid grid-cols-2 gap-2">
          <input
            value={metadata.businessLine}
            onChange={(e) => setMetadata({ ...metadata, businessLine: e.target.value })}
            placeholder="业务线，如车险"
            className="h-9 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />
          <input
            value={metadata.product}
            onChange={(e) => setMetadata({ ...metadata, product: e.target.value })}
            placeholder="产品或主题"
            className="h-9 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />
          <input
            value={metadata.knowledgeVersion}
            onChange={(e) => setMetadata({ ...metadata, knowledgeVersion: e.target.value })}
            placeholder="版本，如 v1.0"
            className="h-9 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />
          <input
            type="date"
            value={metadata.effectiveAt}
            onChange={(e) => setMetadata({ ...metadata, effectiveAt: e.target.value })}
            aria-label="生效日期"
            className="h-9 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />
          <input
            value={metadata.folderPath}
            onChange={(e) => setMetadata({ ...metadata, folderPath: e.target.value })}
            placeholder="所属文件夹，如 车险/理赔"
            className="col-span-2 h-9 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>

        <div className="relative">
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.md,.pdf"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="w-full border-2 border-dashed border-[var(--border-primary)] rounded-xl p-6 text-center hover:border-brand-500/50 transition-colors cursor-pointer disabled:opacity-50"
          >
            <IconUpload className="mx-auto mb-2 text-[var(--text-tertiary)]" />
            <p className="text-sm text-[var(--text-tertiary)]">
              {uploading ? '正在处理...' : '上传保险知识文档'}
            </p>
            <p className="text-xs text-[var(--text-tertiary)] mt-1">支持条款、理赔流程和客服话术</p>
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-[var(--color-error)] bg-[var(--color-error)]/10 rounded-lg px-3 py-2">{error}</p>}

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
            保险知识文档
          </span>
          <button
            onClick={loadDocs}
            className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
          >
            <IconRefresh />
          </button>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 rounded-lg bg-[var(--bg-tertiary)] animate-pulse" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--text-tertiary)]">暂无保险知识文档</p>
            <p className="text-xs text-[var(--text-tertiary)] mt-1">上传保险资料后即可进行知识问答</p>
          </div>
        ) : (
          <div className="space-y-1">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors group">
                <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center shrink-0">
                  <IconFile className="text-[var(--text-tertiary)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[var(--text-primary)] truncate">{doc.filename}</p>
                  {(doc.business_line || doc.product || doc.knowledge_version) && (
                    <p className="text-xs text-[var(--text-tertiary)] truncate">
                      {[doc.folder_path, doc.business_line, doc.product, doc.knowledge_version]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  )}
                  <p className="text-xs text-[var(--text-tertiary)]">
                    {statusLabels[doc.status] || doc.status}
                    {doc.status === 'ready' && ` · ${doc.chunks_count} 个知识片段`}
                  </p>
                </div>
                <span className={`w-2 h-2 rounded-full shrink-0 ${statusColors[doc.status] || statusColors.queued}`} />
                <button
                  onClick={() => handlePreview(doc.id)}
                  disabled={previewLoading}
                  className="shrink-0 rounded px-2 py-1 text-xs text-brand-600 hover:bg-brand-500/10 disabled:opacity-50"
                >
                  预览
                </button>
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="shrink-0 p-1 rounded text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-error)] transition-all"
                >
                  <IconTrash />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedDocument && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" role="dialog" aria-modal="true" aria-label="文档预览">
          <button
            aria-label="关闭预览"
            className="absolute inset-0 cursor-default"
            onClick={() => setSelectedDocument(null)}
          />
          <aside className="relative h-full w-full max-w-2xl overflow-y-auto bg-[var(--bg-primary)] p-6 shadow-2xl">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="truncate text-lg font-semibold text-[var(--text-primary)]">
                  {selectedDocument.filename}
                </p>
                <p className="mt-1 text-sm text-[var(--text-tertiary)]">
                  {[selectedDocument.business_line, selectedDocument.product, selectedDocument.knowledge_version]
                    .filter(Boolean)
                    .join(' · ') || '未填写业务元数据'}
                </p>
              </div>
              <button
                onClick={() => setSelectedDocument(null)}
                aria-label="关闭预览"
                className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              >
                <IconX />
              </button>
            </div>

            <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg bg-[var(--bg-tertiary)] p-3 text-xs text-[var(--text-secondary)]">
              <span>文件类型：{selectedDocument.file_type.toUpperCase()}</span>
              <span>知识片段：{selectedDocument.chunks_count}</span>
              <span>生效日期：{selectedDocument.effective_at?.slice(0, 10) || '未填写'}</span>
              <span>处理状态：{statusLabels[selectedDocument.status] || selectedDocument.status}</span>
            </div>

            <pre className="whitespace-pre-wrap break-words rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-4 font-sans text-sm leading-7 text-[var(--text-primary)]">
              {selectedDocument.content}
            </pre>
          </aside>
        </div>
      )}
    </div>
  )
}
