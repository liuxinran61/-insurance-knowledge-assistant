import { useEffect, useMemo, useState } from 'react'
import type { Document } from '@/types'
import { listDocuments, type KnowledgeQueryFilters } from '@/services/ragService'
import { useChat } from '@/hooks/useChat'
import MessageList from './MessageList'
import ChatInput from './ChatInput'

type QueryScope = 'all' | 'folder' | 'document'

export default function ChatArea() {
  const { messages, isStreaming, sendMessage, newConversation } = useChat()
  const [documents, setDocuments] = useState<Document[]>([])
  const [queryScope, setQueryScope] = useState<QueryScope>('all')
  const [selectedFolderPath, setSelectedFolderPath] = useState('')
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | ''>('')
  const [conversationNotice, setConversationNotice] = useState('连续追问会保留当前对话的上下文')

  useEffect(() => {
    listDocuments().then(setDocuments).catch(() => setDocuments([]))
  }, [])

  const folderPaths = useMemo(() => Array.from(
    new Set(
      documents
        .map((document) => document.folder_path)
        .filter((folderPath): folderPath is string => Boolean(folderPath)),
    ),
  ).sort(), [documents])

  const filters: KnowledgeQueryFilters = queryScope === 'document'
    ? { documentId: selectedDocumentId || undefined }
    : queryScope === 'folder'
      ? { folderPath: selectedFolderPath || undefined }
      : {}

  function handleNewConversation() {
    newConversation()
    setConversationNotice('已开始新对话，上一轮上下文不会继续带入')
  }

  function handleSend(message: string) {
    setConversationNotice('正在基于当前范围检索资料…')
    void sendMessage(message, filters)
  }

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[var(--bg-primary)]">
      <header className="border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] px-4 py-3">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <div>
            <h1 className="text-sm font-semibold text-[var(--text-primary)]">保险售后知识问答</h1>
            <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{conversationNotice}</p>
          </div>
          <button
            onClick={handleNewConversation}
            className="shrink-0 rounded-lg border border-[var(--border-primary)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:border-brand-500 hover:text-brand-600"
          >
            新建对话
          </button>
        </div>
        <div className="mx-auto mt-3 grid max-w-3xl grid-cols-2 gap-2">
          <select
            value={queryScope}
            onChange={(event) => {
              const nextScope = event.target.value as QueryScope
              setQueryScope(nextScope)
              if (nextScope !== 'folder') setSelectedFolderPath('')
              if (nextScope !== 'document') setSelectedDocumentId('')
            }}
            className="h-9 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          >
            <option value="all">提问范围：全部知识库</option>
            <option value="folder">提问范围：指定文件夹</option>
            <option value="document">提问范围：指定文件</option>
          </select>
          {queryScope === 'folder' ? (
            <select
              value={selectedFolderPath}
              onChange={(event) => setSelectedFolderPath(event.target.value)}
              className="h-9 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="">选择文件夹</option>
              {folderPaths.map((folderPath) => <option key={folderPath} value={folderPath}>{folderPath}</option>)}
            </select>
          ) : queryScope === 'document' ? (
            <select
              value={selectedDocumentId}
              onChange={(event) => setSelectedDocumentId(event.target.value ? Number(event.target.value) : '')}
              className="h-9 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="">选择文件</option>
              {documents.map((document) => <option key={document.id} value={document.id}>{document.filename}</option>)}
            </select>
          ) : (
            <div className="flex items-center px-3 text-xs text-[var(--text-tertiary)]">可在此限定提问的知识范围</div>
          )}
        </div>
      </header>
      <MessageList messages={messages} isStreaming={isStreaming} onQuickAsk={handleSend} />
      <ChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  )
}
