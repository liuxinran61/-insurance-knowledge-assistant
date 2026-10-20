export interface User {
  id: number
  username: string
  email: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  has_custom_llm_key: boolean
  llm_provider: string | null
  llm_base_url: string | null
  llm_model_name: string | null
}

export interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  reasoning?: string
  tool_calls?: ToolCall[]
  sources?: KnowledgeSource[]
  timestamp: number
}

export interface KnowledgeSource {
  document_id: number
  chunk_index: number
  filename: string
  business_line: string | null
  product: string | null
  knowledge_version: string | null
  effective_at: string | null
  folder_path: string | null
  excerpt: string
}

export interface ToolCall {
  name: string
  arguments: Record<string, string>
  result?: string
}

export interface SSEChunk {
  reasoning?: string
  content?: string
  error?: string
}

export interface Document {
  id: number
  filename: string
  file_type: string
  business_line: string | null
  product: string | null
  knowledge_version: string | null
  effective_at: string | null
  folder_path: string | null
  status: 'queued' | 'processing' | 'ready' | 'failed'
  chunks_count: number
  processing_task_id: string | null
  error_message: string | null
  created_at: string
}

export interface DocumentDetail extends Document {
  content: string
}

export interface Task {
  id: number
  title: string
  description: string | null
  status: 'pending' | 'in_progress' | 'completed'
  created_at: string
  updated_at: string
}

export interface LLMStats {
  total_calls: number
  successful_calls: number
  failed_calls: number
  total_tokens: number
  total_cost_usd: number
  avg_latency_ms: number
  daily_stats: DailyLLMStats[]
  endpoint_stats: EndpointLLMStats[]
  per_user_stats: UserLLMStats[]
}

export interface DailyLLMStats {
  date: string
  calls: number
  tokens: number
  cost_usd: number
  avg_latency_ms: number
}

export interface EndpointLLMStats {
  endpoint: string
  calls: number
  tokens: number
}

export interface UserLLMStats {
  user_id: number
  calls: number
  tokens: number
  cost_usd: number
}

export interface LLMCallLog {
  id: number
  endpoint: string
  model_name: string
  provider: string
  request_id: string | null
  prompt: string
  response: string | null
  tool_calls: string | null
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  latency_ms: number
  estimated_cost_usd: number
  status: string
  error_message: string | null
  created_at: string
}

export interface HealthStatus {
  status: 'ok' | 'degraded'
  version: string
  dependencies: {
    database: { status: string; error?: string }
    redis: { status: string; error?: string }
    ollama: { status: string; error?: string; models?: string[] }
  }
}

export interface LLMConfig {
  provider?: string
  base_url?: string
  model_name?: string
  api_key?: string
}

export type KnowledgeCategory =
  | 'product'
  | 'claims'
  | 'service'
  | 'compliance'

export type KnowledgePriority =
  | 'normal'
  | 'important'
  | 'urgent'

export type KnowledgeStatus =
  | 'draft'
  | 'published'
  | 'archived'

export interface KnowledgeUpdate {
  id: number
  title: string
  summary: string | null
  content: string
  category: KnowledgeCategory
  priority: KnowledgePriority
  version: string
  status: KnowledgeStatus
  effective_at: string | null
  published_at: string | null
  created_by_id: number
  created_at: string
  updated_at: string
  is_read: boolean
  read_at: string | null
}

export interface KnowledgeUpdateRead {
  id: number
  knowledge_update_id: number
  user_id: number
  read_at: string
}

export interface KnowledgeUpdatePayload {
  title: string
  summary?: string | null
  content: string
  category: KnowledgeCategory
  priority: KnowledgePriority
  version?: string
  effective_at?: string | null
}
