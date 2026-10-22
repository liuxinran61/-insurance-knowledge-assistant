import { useCallback, useState } from 'react'
import type { Message } from '@/types'
import { streamQueryKnowledgeBase, type KnowledgeQueryFilters } from '@/services/ragService'

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

    let receivedContent = false
    let receivedError = false

    try {
      for await (const event of streamQueryKnowledgeBase(content.trim(), 3, filters, sessionId)) {
        if ((event.type === 'content' || event.type === 'content_reset') && event.content) {
          receivedContent = true
        }
        if (event.type === 'error') {
          receivedError = true
        }

        setMessages((previousMessages) => previousMessages.map((message) => {
          if (message.id !== assistantMessage.id) return message

          if (event.type === 'status') {
            return { ...message, activity: event.message }
          }
          if (event.type === 'tool' && event.name) {
            return {
              ...message,
              tool_calls: [
                ...(message.tool_calls || []),
                { name: event.name, arguments: event.arguments || {} },
              ],
            }
          }
          if (event.type === 'content' && event.content) {
            return {
              ...message,
              content: `${message.content}${event.content}`,
              activity: undefined,
            }
          }
          if (event.type === 'content_reset' && event.content) {
            return {
              ...message,
              content: event.content,
              activity: undefined,
            }
          }
          if (event.type === 'sources') {
            return { ...message, sources: event.sources || [], activity: undefined }
          }
          if (event.type === 'error') {
            return {
              ...message,
              content: message.content || '知识库查询失败，请稍后重试。',
              activity: undefined,
            }
          }
          return message
        }))
      }
    } catch {
      receivedError = true
      setMessages((previousMessages) => previousMessages.map((message) => (
        message.id === assistantMessage.id
          ? {
              ...message,
              content: message.content || '知识库查询失败，请稍后重试。',
              activity: undefined,
            }
          : message
      )))
    } finally {
      if (!receivedContent && !receivedError) {
        setMessages((previousMessages) => previousMessages.map((message) => (
          message.id === assistantMessage.id
            ? {
                ...message,
                content: '暂时没有获取到可展示的回答，请换个问法或稍后重试。',
                activity: undefined,
              }
            : message
        )))
      }
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
