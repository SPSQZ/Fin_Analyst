import { env } from './env'
import { supabase } from './supabase'

export class ApiError extends Error {
  readonly status: number
  readonly details: unknown

  constructor(status: number, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

export type StreamEvent = {
  type: string
  text?: string
  message?: string
  citations?: Array<any>
  error?: string
  error_type?: string
}

async function readResponse(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined
  }

  const contentType = response.headers.get('content-type')
  if (contentType?.includes('application/json')) {
    return response.json()
  }

  return response.text()
}

export async function http<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, headers: requestHeaders, ...requestInit } = options
  const { data, error: sessionError } = await supabase.auth.getSession()

  if (sessionError) {
    throw new ApiError(401, 'Unable to read authentication session', sessionError)
  }

  const headers = new Headers(requestHeaders)
  headers.set('Accept', 'application/json')

  if (body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }

  if (data.session?.access_token) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }

  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}/${path.replace(/^\//, '')}`, {
      ...requestInit,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (networkError) {
    throw new ApiError(
      0,
      'Unable to connect to the backend server (Network or CORS error).',
      networkError,
    )
  }

  const responseBody = await readResponse(response)

  if (!response.ok) {
    const message =
      typeof responseBody === 'object' &&
      responseBody !== null &&
      'detail' in responseBody &&
      typeof responseBody.detail === 'string'
        ? responseBody.detail
        : `Request failed with status ${response.status}`

    throw new ApiError(response.status, message, responseBody)
  }

  return responseBody as T
}

export async function stream(
  path: string,
  body: unknown,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const { data, error: sessionError } = await supabase.auth.getSession()

  if (sessionError || !data.session?.access_token) {
    throw new ApiError(401, 'Authentication required', sessionError)
  }

  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}/${path.replace(/^\//, '')}`, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${data.session.access_token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
  } catch (networkError) {
    throw new ApiError(
      0,
      'Unable to connect to the backend server (Network or CORS error).',
      networkError,
    )
  }

  if (!response.ok) {
    const responseBody = await readResponse(response)
    const message =
      typeof responseBody === 'object' &&
      responseBody !== null &&
      'detail' in responseBody &&
      typeof responseBody.detail === 'string'
        ? responseBody.detail
        : `Request failed with status ${response.status}`
    throw new ApiError(response.status, message, responseBody)
  }

  if (!response.body) {
    throw new ApiError(502, 'The streaming response had no body')
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    buffer += value ?? ''

    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''

    for (const rawEvent of events) {
      const dataLine = rawEvent
        .split('\n')
        .find((line) => line.startsWith('data: '))
      if (dataLine) {
        try {
          const parsed = JSON.parse(dataLine.slice(6)) as StreamEvent
          onEvent(parsed)
        } catch {
          // ignore malformed SSE
        }
      }
    }

    if (done) break
  }
}