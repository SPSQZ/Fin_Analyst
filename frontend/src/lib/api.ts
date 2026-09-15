import { http, stream, type StreamEvent } from './http'

export type HealthResponse = {
  status: string
}

export type CurrentUserResponse = {
  id: string
  email: string | null
}

export type ThreadSummary = {
  id: string
  title: string | null
  updated_at: string
}

export type CitationItem = {
  id?: string
  document_chunk_id: string
  quote: string
  relevance_score?: number | null
  ticker?: string | null
  company_name?: string | null
  filing_type?: string | null
  filing_year?: number | null
  filing_date?: string | null
  accession_number?: string | null
  source_url?: string | null
  chunk_index?: number | null
  chunk_metadata?: Record<string, unknown> | null
  content?: string | null
}

export type ChunkDetail = {
  id: string
  chunk_index: number
  content: string
  chunk_metadata?: Record<string, unknown> | null
  ticker?: string | null
  company_name?: string | null
  filing_type?: string | null
  filing_year?: number | null
  filing_date?: string | null
  accession_number?: string | null
  source_url?: string | null
  surrounding?: Array<{
    id: string
    chunk_index: number
    content: string
    is_current: boolean
  }>
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  parts: Array<Record<string, unknown>> | null
  sequence: number
  created_at: string
  citations?: CitationItem[]
  grounding_status?: 'verified' | 'unverified' | 'failed'
}

export type ThreadDetail = ThreadSummary & {
  messages: ChatMessage[]
}

export const api = {
  health: () => http<HealthResponse>('/health'),
  currentUser: () => http<CurrentUserResponse>('/me'),
  listThreads: () => http<ThreadSummary[]>('/chat/threads'),
  createThread: (title?: string) =>
    http<ThreadSummary>('/chat/threads', {
      method: 'POST',
      body: { title: title || null },
    }),
  getThread: (threadId: string) =>
    http<ThreadDetail>(`/chat/threads/${threadId}`),
  deleteThread: (threadId: string) =>
    http<void>(`/chat/threads/${threadId}`, { method: 'DELETE' }),
  getChunk: (chunkId: string, window = 0) =>
    http<ChunkDetail>(`/chat/chunks/${chunkId}?window=${window}`),
  streamChat: (
    threadId: string,
    messages: Array<{ role: string; content: string }>,
    onEvent: (event: StreamEvent) => void,
  ) => stream('/chat/stream', { thread_id: threadId, messages }, onEvent),
}