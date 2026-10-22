import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '@/types'
import ToolCallCard from './ToolCallCard'
import { IconUser } from '@/components/ui/Icons'

interface MessageListProps {
  messages: Message[]
  isStreaming: boolean
  onQuickAsk?: (question: string) => void
}

export default function MessageList({ messages, isStreaming, onQuickAsk }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const activeAssistantMessage = [...messages]
    .reverse()
    .find((message) => message.role === 'assistant')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return <EmptyState onQuickAsk={onQuickAsk} />
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto py-6 px-4 space-y-6">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && !activeAssistantMessage?.activity && (
          <div className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
            正在输出回答…
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  if (message.role === 'user') {
    return (
      <div className="flex items-start justify-end gap-3">
        <div className="max-w-[70%] bg-brand-500 text-white rounded-2xl rounded-br-md px-4 py-2.5">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-brand-500/20 flex items-center justify-center shrink-0 mt-1">
          <IconUser className="text-brand-500" />
        </div>
      </div>
    )
  }

  if (message.role === 'system') {
    return null
  }

  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center shrink-0 mt-1">
        <span className="text-white text-xs font-bold">保</span>
      </div>
      <div className="flex-1 min-w-0 space-y-3">
        {message.activity && (
          <div className="flex items-center gap-2 text-xs text-brand-600 dark:text-brand-400">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" />
            {message.activity}
          </div>
        )}
        {message.reasoning && (
          <ReasoningBlock content={message.reasoning} />
        )}
        {message.content && (
          <div className="prose prose-sm max-w-none text-[var(--text-primary)]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        {message.tool_calls?.map((tc, i) => (
          <ToolCallCard key={i} toolCall={tc} />
        ))}
        {message.sources && message.sources.length > 0 && (
          <div className="border-t border-[var(--border-primary)] pt-3">
            <p className="mb-2 text-xs font-medium text-[var(--text-tertiary)]">
              回答依据（{message.sources.length}）
            </p>
            <div className="space-y-2">
              {message.sources.map((source) => (
                <div
                  key={`${source.document_id}-${source.chunk_index}`}
                  className="rounded-lg bg-[var(--bg-tertiary)] p-2.5"
                >
                  <p className="text-xs font-medium text-[var(--text-secondary)]">{source.filename}</p>
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    {[source.folder_path, source.product, source.knowledge_version, source.effective_at?.slice(0, 10)]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-[var(--text-tertiary)]">
                    {source.excerpt}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function ReasoningBlock({ content }: { content: string }) {
  return (
    <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 overflow-hidden">
      <details className="group">
        <summary className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-yellow-600 dark:text-yellow-400 cursor-pointer hover:bg-yellow-500/5 transition-colors">
          <svg className="w-3.5 h-3.5 group-open:rotate-90 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
          思考过程
        </summary>
        <div className="px-3 pb-3 text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      </details>
    </div>
  )
}

function EmptyState({ onQuickAsk }: { onQuickAsk?: (question: string) => void }) {
  const quickQuestions = [
    { label: '车险客户报案后，标准理赔流程是什么？', icon: '🚗' },
    { label: '健康险等待期内出险，应该如何向客户解释？', icon: '🏥' },
    { label: '客户申请退保，需要确认哪些信息和风险？', icon: '📋' },
    { label: '最近有哪些需要客服关注的知识更新？', icon: '🔔' },
  ]

  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-brand-500/10 flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
          保险售后知识问答
        </h2>
        <p className="text-sm text-[var(--text-tertiary)] mb-6">
          从保险条款、理赔流程和售后服务规范开始学习
        </p>
        <div className="grid grid-cols-1 gap-2">
          {quickQuestions.map((q) => (
            <button
              key={q.label}
              onClick={() => onQuickAsk?.(q.label)}
              className="flex items-center gap-3 w-full px-4 py-2.5 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] hover:border-brand-500/30 text-left transition-all duration-200 group"
            >
              <span className="text-base shrink-0">{q.icon}</span>
              <span className="text-sm text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
                {q.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
