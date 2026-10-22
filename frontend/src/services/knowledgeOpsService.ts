import api from './api'
import type { KnowledgeOpsRunResult } from '@/types'

export async function runKnowledgeOpsAgent(
  query: string,
): Promise<KnowledgeOpsRunResult> {
  const response = await api.post<KnowledgeOpsRunResult>(
    '/knowledge-ops/run',
    { query },
  )

  return response.data
}
