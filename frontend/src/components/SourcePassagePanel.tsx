import { useEffect, useState } from 'react'
import { Check, Copy, ExternalLink, FileText, Layers, ShieldCheck, X } from 'lucide-react'
import { api, type ChunkDetail, type CitationItem } from '../lib/api'

interface SourcePassagePanelProps {
  citation: CitationItem | null
  onClose: () => void
}

export function SourcePassagePanel({ citation, onClose }: SourcePassagePanelProps) {
  const [copied, setCopied] = useState(false)
  const [loadingContext, setLoadingContext] = useState(false)
  const [chunkDetail, setChunkDetail] = useState<ChunkDetail | null>(null)
  const [showSurrounding, setShowSurrounding] = useState(false)

  // Listen for Escape key to close the panel
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // Reset expanded chunk state when citation changes
  useEffect(() => {
    setChunkDetail(null)
    setShowSurrounding(false)
    setCopied(false)
  }, [citation?.document_chunk_id])

  if (!citation) return null

  const handleCopyQuote = async () => {
    try {
      await navigator.clipboard.writeText(citation.quote)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
    }
  }

  const handleLoadSurrounding = async () => {
    if (chunkDetail?.surrounding) {
      setShowSurrounding(!showSurrounding)
      return
    }

    setLoadingContext(true)
    try {
      const detail = await api.getChunk(citation.document_chunk_id, 1)
      setChunkDetail(detail)
      setShowSurrounding(true)
    } catch {
      // ignore
    } finally {
      setLoadingContext(false)
    }
  }

  // Render text with the quoted sentence highlighted
  const renderHighlightedPassage = (content: string, quote: string) => {
    if (!content) return <p className="text-sm text-slate-400 italic">No chunk content available.</p>

    const trimmedQuote = quote.trim()
    const quoteIndex = content.indexOf(trimmedQuote)

    if (quoteIndex === -1 || !trimmedQuote) {
      return <p className="source-passage-content">{content}</p>
    }

    const before = content.slice(0, quoteIndex)
    const match = content.slice(quoteIndex, quoteIndex + trimmedQuote.length)
    const after = content.slice(quoteIndex + trimmedQuote.length)

    return (
      <p className="source-passage-content">
        {before}
        <mark className="source-highlighted-mark" title="Exact cited passage">
          {match}
        </mark>
        {after}
      </p>
    )
  }

  const contentToDisplay = citation.content || chunkDetail?.content || ''

  return (
    <aside className="source-inspector-panel animate-slide-right" aria-label="Source Document Inspector">
      <header className="source-inspector-header">
        <div className="source-meta-block">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="badge-ticker">{citation.ticker || 'FILING'}</span>
            <span className="badge-type">{citation.filing_type || '10-K'}</span>
            {citation.filing_year && (
              <span className="badge-year">FY{citation.filing_year}</span>
            )}
            {citation.chunk_index !== null && citation.chunk_index !== undefined && (
              <span className="badge-section">Chunk #{citation.chunk_index}</span>
            )}
          </div>
          <h3 className="source-company-name">
            {citation.company_name || `${citation.ticker || 'SEC'} Filing`}
          </h3>
          {citation.filing_date && (
            <p className="source-filing-date">
              Reported: {new Date(citation.filing_date).toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              })}
            </p>
          )}
        </div>
        <button
          type="button"
          className="btn-icon-close"
          onClick={onClose}
          aria-label="Close source inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </header>

      <div className="source-inspector-scrollable">
        {/* Verified Quote Box */}
        <section className="verified-claim-box">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              VERIFIED CLAIM QUOTE
            </span>
            <button
              type="button"
              className="btn-copy-quote"
              onClick={handleCopyQuote}
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy Quote</span>
                </>
              )}
            </button>
          </div>
          <blockquote className="verified-quote-text">
            “{citation.quote}”
          </blockquote>
        </section>

        {/* SEC EDGAR External Link */}
        {citation.source_url && (
          <div className="edgar-link-wrapper">
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="edgar-link-btn"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>View Original on SEC EDGAR</span>
              <ExternalLink className="w-3 h-3 ml-auto" />
            </a>
          </div>
        )}

        {/* Filing Passage Section */}
        <section className="underlying-passage-section">
          <div className="flex items-center justify-between gap-2 mb-2.5">
            <h4 className="passage-section-heading">Underlying Filing Passage</h4>
            <button
              type="button"
              className="btn-expand-context"
              onClick={handleLoadSurrounding}
              disabled={loadingContext}
            >
              <Layers className="w-3.5 h-3.5" />
              {loadingContext
                ? 'Loading...'
                : showSurrounding
                  ? 'Collapse Context'
                  : 'Expand Context (±1 chunk)'}
            </button>
          </div>

          <div className="passage-text-container">
            {showSurrounding && chunkDetail?.surrounding ? (
              <div className="surrounding-chunks-list">
                {chunkDetail.surrounding.map((neighbor) => (
                  <div
                    key={neighbor.id}
                    className={`neighbor-chunk-item ${neighbor.id === citation.document_chunk_id ? 'neighbor-chunk-primary' : ''}`}
                  >
                    <div className="neighbor-chunk-badge">
                      Section #{neighbor.chunk_index}
                      {neighbor.id === citation.document_chunk_id ? ' (Cited Chunk)' : ''}
                    </div>
                    {neighbor.id === citation.document_chunk_id
                      ? renderHighlightedPassage(neighbor.content, citation.quote)
                      : <p className="source-passage-content">{neighbor.content}</p>
                    }
                  </div>
                ))}
              </div>
            ) : (
              renderHighlightedPassage(contentToDisplay, citation.quote)
            )}
          </div>
        </section>
      </div>
    </aside>
  )
}
