import api from './api'
import type {
  KnowledgeUpdate,
  KnowledgeUpdateRead,
  KnowledgeUpdatePayload,
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

export async function listAdminKnowledgeUpdates(
  skip = 0,
  limit = 100,
): Promise<KnowledgeUpdate[]> {
  const response = await api.get<KnowledgeUpdate[]>(
    '/knowledge-updates/admin',
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
export async function createKnowledgeUpdate(
  payload: KnowledgeUpdatePayload,
): Promise<KnowledgeUpdate> {
  const response = await api.post<KnowledgeUpdate>(
    '/knowledge-updates/',
    payload,
  )

  return response.data
}

export async function updateKnowledgeUpdate(
  knowledgeUpdateId: number,
  payload: Partial<KnowledgeUpdatePayload>,
): Promise<KnowledgeUpdate> {
  const response = await api.patch<KnowledgeUpdate>(
    `/knowledge-updates/${knowledgeUpdateId}`,
    payload,
  )

  return response.data
}

export async function publishKnowledgeUpdate(
  knowledgeUpdateId: number,
): Promise<KnowledgeUpdate> {
  const response = await api.post<KnowledgeUpdate>(
    `/knowledge-updates/${knowledgeUpdateId}/publish`,
  )

  return response.data
}
