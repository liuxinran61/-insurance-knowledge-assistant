import { useCallback, useState } from 'react'
import type { Message } from '@/types'
import { queryKnowledgeBase, type KnowledgeQueryFilters } from '@/services/ragService'

const SESSION_STORAGE_KEY = 'knowledge_chat_session_id'

function generateId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function getOrCreateSessionId(): string {
  const existingSessionId = localStorage.getItem(SESSION_STORAGE_KEY)
  if (existingSessionId) return existingSessionId

  const sessionId = crypto.randomUUID()
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId)
  return sessionId
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionId, setSessionId] = useState(getOrCreateSessionId)

  const sendMessage = useCallback(async (
    content: string,
    filters: KnowledgeQueryFilters = {},
  ) => {
    if (!content.trim() || isStreaming) return

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      timestamp: Date.now(),
    }
    const assistantMessage: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }

    setMessages((previousMessages) => [...previousMessages, userMessage, assistantMessage])
    setIsStreaming(true)

    try {
      const result = await queryKnowledgeBase(content.trim(), 3, filters, sessionId)
      setMessages((previousMessages) => previousMessages.map((message) => (
        message.id === assistantMessage.id
          ? { ...message, content: result.answer, sources: result.sources }
          : message
      )))
    } catch {
      setMessages((previousMessages) => previousMessages.map((message) => (
        message.id === assistantMessage.id
          ? { ...message, content: '知识库查询失败，请稍后重试。' }
          : message
      )))
    } finally {
      setIsStreaming(false)
    }
  }, [isStreaming, sessionId])

  const newConversation = useCallback(() => {
    const nextSessionId = crypto.randomUUID()
    localStorage.setItem(SESSION_STORAGE_KEY, nextSessionId)
    setSessionId(nextSessionId)
    setMessages([])
  }, [])

  return {
    messages,
    isStreaming,
    sendMessage,
    newConversation,
  }
}
