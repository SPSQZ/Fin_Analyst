import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import {
  Activity,
  ArrowUp,
  CheckCircle2,
  Database,
  LogOut,
  MessageSquare,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
} from 'lucide-react'

import { useAuth } from '../auth/useAuth'
import { CitationChip } from '../components/CitationChip'
import { EmptyState } from '../components/EmptyState'
import { ErrorAlert } from '../components/ErrorAlert'
import { LoadingStatus } from '../components/LoadingStatus'
import { PipelineTelemetryPanel } from '../components/PipelineTelemetryPanel'
import { SourcePassagePanel } from '../components/SourcePassagePanel'
import { api, type ChatMessage, type CitationItem, type ThreadSummary } from '../lib/api'
import { ApiError } from '../lib/http'
import { supabase } from '../lib/supabase'

interface MessageProps {
  message: ChatMessage
  selectedCitation: CitationItem | null
  onSelectCitation: (citation: CitationItem) => void
  streamingStatus?: string | null
}

function Message({ message, selectedCitation, onSelectCitation, streamingStatus }: MessageProps) {
  const isAssistant = message.role === 'assistant'
  const hasCitations = isAssistant && message.citations && message.citations.length > 0
  const isStreaming = isAssistant && streamingStatus !== undefined && streamingStatus !== null
  const hasContent = !!message.content

  return (
    <article className={`chat-message ${message.role}`}>
      <div className="message-header-row">
        <div className="flex items-center gap-2">
          {message.role === 'user' ? (
            <div className="role-avatar user-avatar">
              <span>AN</span>
            </div>
          ) : (
            <div className="role-avatar assistant-avatar">
              <Sparkles className="w-3.5 h-3.5 text-cyan-300" />
            </div>
          )}
          <span className="message-role">
            {message.role === 'user' ? 'Senior Analyst' : 'Copilot · SEC Research Agent'}
          </span>
        </div>

        {hasCitations && (
          <span className="grounded-tag">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Grounded in SEC Filings</span>
          </span>
        )}
      </div>

      <div className="message-body">
        {isStreaming && !hasContent && (
          <LoadingStatus statusText={streamingStatus || undefined} />
        )}
        {hasContent && (
          <div className="markdown-content">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}
      </div>

      {hasCitations && (
        <div className="message-citations-section">
          <div className="citations-header">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span className="citations-label">Verified SEC Filings & Claims</span>
          </div>
          <div className="citations-list">
            {message.citations!.map((citation, idx) => (
              <CitationChip
                key={citation.id || citation.document_chunk_id || idx}
                citation={citation}
                index={idx}
                isActive={selectedCitation?.document_chunk_id === citation.document_chunk_id}
                onClick={onSelectCitation}
              />
            ))}
          </div>
        </div>
      )}
    </article>
  )
}

export function ChatPage() {
  const { threadId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [streamingStatus, setStreamingStatus] = useState<string | null>(null)
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null)
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true)
  const [errorState, setErrorState] = useState<{
    message: string
    type?: 'auth-expired' | 'retrieval-failure' | 'grounding-failure' | 'network-cors' | 'provider-unavailable' | 'general'
  } | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom of messages viewport on updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingStatus])

  // Load threads and active thread messages
  useEffect(() => {
    let mounted = true

    void api.listThreads()
      .then(async (nextThreads) => {
        if (!mounted) return
        setLoading(false)
        setErrorState(null)
        setThreads(nextThreads)
        if (threadId) {
          const thread = await api.getThread(threadId)
          if (mounted) setMessages(thread.messages)
        } else if (nextThreads[0]) {
          navigate(`/chat/${nextThreads[0].id}`, { replace: true })
        }
      })
      .catch((requestError: unknown) => {
        if (mounted) {
          setLoading(false)
          handleError(requestError, 'Unable to load conversations')
        }
      })

    return () => {
      mounted = false
    }
  }, [navigate, threadId])

  function handleError(requestError: unknown, fallbackMessage = 'An error occurred') {
    if (requestError instanceof ApiError) {
      if (requestError.status === 401) {
        setErrorState({ message: 'Your session has expired. Please sign in again.', type: 'auth-expired' })
      } else if (requestError.status === 0) {
        setErrorState({
          message: 'Unable to connect to backend server. Please verify the API is running at http://127.0.0.1:8000.',
          type: 'network-cors',
        })
      } else {
        setErrorState({ message: `${requestError.message} (HTTP ${requestError.status})`, type: 'general' })
      }
    } else if (requestError instanceof Error) {
      setErrorState({ message: requestError.message, type: 'general' })
    } else {
      setErrorState({ message: fallbackMessage, type: 'general' })
    }
  }

  async function createNewThread() {
    setErrorState(null)
    setSelectedCitation(null)
    try {
      const thread = await api.createThread('New Research Thread')
      setThreads((current) => [thread, ...current])
      setMessages([])
      navigate(`/chat/${thread.id}`)
    } catch (requestError) {
      handleError(requestError, 'Unable to create new thread')
    }
  }

  async function handleDeleteThread(threadIdToDelete: string, e: React.MouseEvent) {
    e.stopPropagation()
    setErrorState(null)

    // Optimistically update threads list
    const remaining = threads.filter((t) => t.id !== threadIdToDelete)
    setThreads(remaining)

    // If the active thread was deleted, navigate away
    if (threadId === threadIdToDelete) {
      setSelectedCitation(null)
      setMessages([])
      if (remaining.length > 0) {
        navigate(`/chat/${remaining[0].id}`, { replace: true })
      } else {
        navigate('/chat', { replace: true })
      }
    }

    try {
      await api.deleteThread(threadIdToDelete)
    } catch (requestError) {
      handleError(requestError, 'Unable to delete conversation')
    }
  }

  async function sendMessage(textToSend?: string) {
    const content = (textToSend !== undefined ? textToSend : draft).trim()
    if (!content || sending) return

    setErrorState(null)
    setSending(true)
    setStreamingStatus('Extracting financial terms & analyzing filing index...')
    let activeThreadId = threadId

    try {
      if (!activeThreadId) {
        const thread = await api.createThread(content.slice(0, 60))
        activeThreadId = thread.id
        setThreads((current) => [thread, ...current])
        navigate(`/chat/${thread.id}`, { replace: true })
      }
      if (!activeThreadId) throw new Error('Unable to determine the active thread')

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        parts: null,
        sequence: messages.length,
        created_at: new Date().toISOString(),
      }
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        parts: null,
        sequence: messages.length + 1,
        created_at: new Date().toISOString(),
        citations: [],
      }
      setMessages((current) => [...current, userMessage, assistantMessage])
      setDraft('')

      await api.streamChat(
        activeThreadId,
        [{ role: 'user', content }],
        (event) => {
          if (event.type === 'status' && event.message) {
            setStreamingStatus(event.message)
          } else if (event.type === 'text-delta' && event.text) {
            setMessages((current) => {
              const next = [...current]
              const last = next[next.length - 1]
              if (last?.role === 'assistant') {
                next[next.length - 1] = { ...last, content: last.content + event.text }
              }
              return next
            })
          } else if (event.type === 'citations' && Array.isArray(event.citations)) {
            setMessages((current) => {
              const next = [...current]
              const last = next[next.length - 1]
              if (last?.role === 'assistant') {
                next[next.length - 1] = { ...last, citations: event.citations as CitationItem[] }
              }
              return next
            })
          } else if (event.type === 'error' && event.error) {
            setErrorState({
              message: event.error,
              type: (event.error_type as any) || 'general',
            })
          } else if (event.type === 'finish') {
            setStreamingStatus(null)
          }
        },
      )
    } catch (requestError) {
      handleError(requestError, 'Unable to complete analysis')
    } finally {
      setSending(false)
      setStreamingStatus(null)
    }
  }

  // Filter threads by search query
  const filteredThreads = threads.filter((t) =>
    (t.title || 'Untitled conversation').toLowerCase().includes(searchQuery.toLowerCase())
  )

  const activeThread = threads.find((t) => t.id === threadId)

  return (
    <div className="terminal-app-shell">
      {/* 1. Left Panel: Chat Threads & History */}
      <aside className="left-panel-sidebar" aria-label="Conversation History">
        {/* Brand Header */}
        <div className="terminal-brand-header">
          <div className="flex items-center gap-2.5">
            <div className="brand-logo-badge">
              <Terminal className="w-4 h-4 text-cyan-400" />
            </div>
            <div>
              <h1 className="brand-title">SEC Copilot</h1>
              <p className="brand-subtitle">Financial Terminal</p>
            </div>
          </div>
          <div className="corpus-live-indicator" title="Corpus: Apple Inc. (AAPL) FY2024 10-K Ingested">
            <span className="live-dot" />
            <span>AAPL 10-K</span>
          </div>
        </div>

        {/* Action: New Research Thread */}
        <div className="new-thread-action-container">
          <button
            type="button"
            className="btn-new-thread"
            onClick={() => void createNewThread()}
            aria-label="Create new research conversation"
          >
            <Plus className="w-4 h-4" />
            <span>New Research Thread</span>
          </button>
        </div>

        {/* Search Conversations */}
        <div className="thread-search-box">
          <Search className="w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="thread-search-input"
          />
        </div>

        {/* Conversations List */}
        <div className="thread-history-list">
          <div className="thread-list-section-header">
            <span>RESEARCH THREADS</span>
            <span className="thread-count-badge">{filteredThreads.length}</span>
          </div>

          {filteredThreads.map((thread) => {
            const isActive = thread.id === threadId
            return (
              <div
                key={thread.id}
                className={`thread-item-wrapper ${isActive ? 'active' : ''}`}
              >
                <button
                  type="button"
                  className="thread-item-btn"
                  onClick={() => {
                    setSelectedCitation(null)
                    navigate(`/chat/${thread.id}`)
                  }}
                >
                  <div className="thread-item-icon">
                    <MessageSquare className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  </div>
                  <div className="thread-item-content">
                    <span className="thread-item-title">{thread.title || 'Untitled Research'}</span>
                    <span className="thread-item-date">
                      {new Date(thread.updated_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                      })}
                    </span>
                  </div>
                </button>
                <button
                  type="button"
                  className="btn-delete-thread"
                  title="Delete conversation"
                  aria-label="Delete conversation"
                  onClick={(e) => void handleDeleteThread(thread.id, e)}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )
          })}

          {!filteredThreads.length && !loading && (
            <div className="no-threads-hint">
              <p className="text-xs text-slate-400">No matching conversations found.</p>
            </div>
          )}
        </div>

        {/* User Account / Sign Out Footer */}
        <div className="sidebar-user-footer">
          <div className="user-profile-card">
            <div className="user-avatar-circle">
              <span>{user?.email?.slice(0, 2).toUpperCase() || 'AN'}</span>
            </div>
            <div className="user-info-text">
              <p className="user-email-text">{user?.email}</p>
              <p className="user-role-text">Equity Analyst</p>
            </div>
            <button
              type="button"
              className="btn-signout-icon"
              title="Sign out of workstation"
              onClick={() => void supabase.auth.signOut()}
            >
              <LogOut className="w-4 h-4 text-slate-400 hover:text-red-400" />
            </button>
          </div>
        </div>
      </aside>

      {/* 2. Center Panel: Full Browser Chat Canvas with Levitating Question Bar */}
      <section className="center-chat-canvas" aria-label="Research Canvas">
        {/* Canvas Top Bar */}
        <header className="canvas-header-bar">
          <div className="flex items-center gap-3">
            <div>
              <h2 className="canvas-thread-title">
                {activeThread?.title || 'Filing Analysis Workspace'}
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="filing-meta-pill">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  Apple Inc. (AAPL) · FY2024 Form 10-K
                </span>
                <span className="filing-meta-pill hidden sm:inline-flex">
                  100 Chunks Ingested · 768-dim HNSW
                </span>
              </div>
            </div>
          </div>

          <div className="canvas-header-actions">
            {/* Toggle Right Telemetry Panel */}
            <button
              type="button"
              className={`btn-telemetry-toggle ${isRightPanelOpen ? 'active' : ''}`}
              onClick={() => setIsRightPanelOpen(!isRightPanelOpen)}
              title={isRightPanelOpen ? 'Hide Execution Telemetry' : 'Show Execution Telemetry'}
            >
              <Activity className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden md:inline">Execution Pipeline</span>
              {isRightPanelOpen ? (
                <PanelRightClose className="w-3.5 h-3.5 opacity-70" />
              ) : (
                <PanelRightOpen className="w-3.5 h-3.5 opacity-70" />
              )}
            </button>
          </div>
        </header>

        {/* Error Alert wrapper */}
        {errorState && (
          <div className="chat-error-wrapper">
            <ErrorAlert
              error={errorState.message}
              errorType={errorState.type}
              onRetry={() => {
                setErrorState(null)
                if (messages.length > 0 && messages[messages.length - 1].role === 'user') {
                  void sendMessage(messages[messages.length - 1].content)
                }
              }}
              onDismiss={() => setErrorState(null)}
            />
          </div>
        )}

        {/* Messages Stream Scroll Area */}
        <div className="messages-stream-viewport">
          <div className="messages-stream-container">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="flex items-center gap-3 text-slate-400">
                  <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                  <span>Loading research conversation...</span>
                </div>
              </div>
            ) : !messages.length ? (
              <EmptyState
                type="empty-conversation"
                onSelectPrompt={(prompt) => {
                  setDraft(prompt)
                  void sendMessage(prompt)
                }}
              />
            ) : (
              messages.map((message, msgIdx) => (
                <Message
                  key={message.id}
                  message={message}
                  selectedCitation={selectedCitation}
                  onSelectCitation={(citation) => setSelectedCitation(citation)}
                  streamingStatus={
                    sending && msgIdx === messages.length - 1 && message.role === 'assistant'
                      ? streamingStatus
                      : undefined
                  }
                />
              ))
            )}
            <div ref={messagesEndRef} className="messages-scroll-anchor" />
          </div>
        </div>

        {/* 2. Levitating Floating Question Bar */}
        <div className="levitating-bar-wrapper">
          <form
            className="levitating-bar"
            onSubmit={(event) => {
              event.preventDefault()
              void sendMessage()
            }}
          >
            {/* Top Bar inside capsule */}
            <div className="levitating-top-row">
              <div className="flex items-center gap-2">
                <Sparkles className="w-3 h-3 text-cyan-400" />
                <span className="engine-badge">gemini-3.5-flash · Hybrid RRF Fused · Exact Quotes</span>
              </div>
              {sending && (
                <div className="flex items-center gap-1.5 text-xs text-cyan-400">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                  <span>Streaming SEC Response...</span>
                </div>
              )}
            </div>

            {/* Input & Send Action Row */}
            <div className="levitating-input-row">
              <textarea
                ref={textareaRef}
                aria-label="Message Input"
                disabled={sending}
                placeholder="Ask about Apple's net sales, Services margins, risk factors, or litigation..."
                rows={1}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    e.currentTarget.form?.requestSubmit()
                  }
                }}
                className="levitating-textarea"
              />
              <button
                type="submit"
                disabled={sending || !draft.trim()}
                className="btn-levitating-send"
                title="Send query (Enter)"
                aria-label="Send query"
              >
                {sending ? (
                  <Activity className="w-4 h-4 animate-spin text-cyan-300" />
                ) : (
                  <ArrowUp className="w-4 h-4 text-white" />
                )}
              </button>
            </div>

            {/* Micro Helper / Shortcut info */}
            <div className="levitating-bottom-row">
              <span className="shortcut-hint">Press <strong>Enter ↵</strong> to submit · <strong>Shift + Enter</strong> for newline</span>
              <span className="grounding-guarantee">Anti-Hallucination Guardrail Active</span>
            </div>
          </form>
        </div>
      </section>

      {/* 3. Right Panel: Real-Time Background Execution Pipeline */}
      {isRightPanelOpen && (
        <aside className="right-panel-telemetry" aria-label="Execution Telemetry">
          <PipelineTelemetryPanel
            currentStatus={streamingStatus}
            isStreaming={sending}
            lastExtractedTerms={['total net sales', 'fiscal 2024', 'Services']}
            chunksFoundCount={4}
            citationsCount={3}
          />
        </aside>
      )}

      {/* 4. Dedicated Panel: Source Passage & Verified Claim Inspector */}
      {selectedCitation && (
        <div className="source-inspector-overlay">
          <div className="source-inspector-backdrop" onClick={() => setSelectedCitation(null)} />
          <div className="source-inspector-slider">
            <SourcePassagePanel
              citation={selectedCitation}
              onClose={() => setSelectedCitation(null)}
            />
          </div>
        </div>
      )}
    </div>
  )
}