import { Sparkles } from 'lucide-react'

interface LoadingStatusProps {
  statusText?: string
}

export function LoadingStatus({ statusText }: LoadingStatusProps) {
  const message = statusText || 'Searching SEC filings & analyzing evidence...'

  return (
    <div className="streaming-status-chip" role="status" aria-live="polite">
      <Sparkles className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
      <span className="streaming-status-label">{message}</span>
      <span className="inline-flex gap-0.5 text-cyan-400 font-mono">
        <span className="animate-bounce">.</span>
        <span className="animate-bounce [animation-delay:0.15s]">.</span>
        <span className="animate-bounce [animation-delay:0.3s]">.</span>
      </span>
    </div>
  )
}
