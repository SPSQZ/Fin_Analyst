import { ExternalLink, FileText } from 'lucide-react'
import type { CitationItem } from '../lib/api'

interface CitationChipProps {
  citation: CitationItem
  index: number
  isActive?: boolean
  onClick: (citation: CitationItem) => void
}

export function CitationChip({ citation, index, isActive = false, onClick }: CitationChipProps) {
  const ticker = citation.ticker || 'SEC'
  const filingType = citation.filing_type || '10-K'
  const year = citation.filing_year ? `'${String(citation.filing_year).slice(-2)}` : ''
  const chunkNumber = citation.chunk_index !== null && citation.chunk_index !== undefined
    ? `§${citation.chunk_index}`
    : ''

  const label = `${ticker} ${filingType} ${year} ${chunkNumber}`.trim()
  const title = citation.company_name
    ? `${citation.company_name} — Quote: "${citation.quote.slice(0, 80)}..."`
    : `Quote: "${citation.quote.slice(0, 80)}..."`

  return (
    <button
      type="button"
      className={`citation-chip-btn ${isActive ? 'citation-chip-active' : ''}`}
      onClick={() => onClick(citation)}
      title={title}
      aria-label={`View source passage ${index + 1}: ${label}`}
    >
      <span className="citation-num">{index + 1}</span>
      <FileText className="w-3 h-3 text-cyan-400 opacity-80" />
      <span className="citation-label">{label}</span>
      <ExternalLink className="w-2.5 h-2.5 opacity-60 ml-0.5" />
    </button>
  )
}
