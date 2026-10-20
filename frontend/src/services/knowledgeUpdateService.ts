import api from './api'
import type {
  KnowledgeUpdate,
  KnowledgeUpdateRead,
} from '@/types'

export async function listKnowledgeUpdates(
  skip = 0,
  limit = 50,
): Promise<KnowledgeUpdate[]> {
  const response = await api.get<KnowledgeUpdate[]>(
    '/knowledge-updates/',
    {
      params: { skip, limit },
    },
  )

  return response.data
}

export async function markKnowledgeUpdateAsRead(
  knowledgeUpdateId: number,
): Promise<KnowledgeUpdateRead> {
  const response = await api.post<KnowledgeUpdateRead>(
    `/knowledge-updates/${knowledgeUpdateId}/read`,
  )

  return response.data
}