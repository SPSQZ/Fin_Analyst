import { ArrowUpRight, BarChart3, Building2, Cpu, FileText, PlusCircle, ShieldAlert } from 'lucide-react'

interface EmptyStateProps {
  type: 'no-threads' | 'empty-conversation' | 'no-corpus-match'
  onSelectPrompt?: (prompt: string) => void
  onCreateThread?: () => void
}

export function EmptyState({ type, onSelectPrompt, onCreateThread }: EmptyStateProps) {
  if (type === 'no-threads') {
    return (
      <div className="empty-state-card-container">
        <div className="empty-icon-box">
          <FileText className="w-8 h-8 text-cyan-400" />
        </div>
        <h3 className="empty-title">No research conversations yet</h3>
        <p className="empty-subtitle">
          Start a new conversation to query SEC 10-K filings with verbatim citation grounding.
        </p>
        {onCreateThread && (
          <button type="button" className="btn-primary-action" onClick={onCreateThread}>
            <PlusCircle className="w-4 h-4" />
            <span>New Research Thread</span>
          </button>
        )}
      </div>
    )
  }

  if (type === 'no-corpus-match') {
    return (
      <div className="no-corpus-card">
        <div className="flex items-center gap-2 mb-2">
          <ShieldAlert className="w-5 h-5 text-amber-400" />
          <h4 className="font-semibold text-amber-300">No matching filings in local index</h4>
        </div>
        <p className="text-sm text-slate-300 mb-3">
          The Copilot searches our high-precision SEC 10-K database. Indexed companies include:
        </p>
        <div className="flex flex-wrap gap-2 mb-3">
          <span className="pill-ticker">AAPL · Apple Inc. (FY2021–2024)</span>
          <span className="pill-ticker">MSFT · Microsoft Corp. (FY2021–2025)</span>
          <span className="pill-ticker">NVDA · NVIDIA Corp. (FY2021–2024)</span>
          <span className="pill-ticker">AMZN · Amazon.com (FY2021–2025)</span>
          <span className="pill-ticker">GOOGL · Alphabet Inc. (FY2021–2025)</span>
        </div>
        <p className="text-xs text-slate-400">
          Try asking specifically about one of these tickers, revenue metrics, or risk disclosures.
        </p>
      </div>
    )
  }

  // 'empty-conversation'
  const suggestedPrompts = [
    {
      icon: BarChart3,
      tag: 'Apple Revenue',
      title: 'Fiscal 2024 Net Sales & iPhone Performance',
      text: "What was Apple's total net sales in fiscal 2024 and how did iPhone sales perform?",
    },
    {
      icon: ShieldAlert,
      tag: 'NVIDIA Risks',
      title: 'Supply Chain & Foundry Concentration',
      text: "What are NVIDIA's main supply chain and manufacturing concentration risks outlined in their 2024 10-K?",
    },
    {
      icon: Cpu,
      tag: 'Microsoft Cloud',
      title: 'Intelligent Cloud & Azure Expansion',
      text: "Summarize Microsoft's Intelligent Cloud revenue and Azure growth drivers in fiscal 2024.",
    },
    {
      icon: Building2,
      tag: 'Apple R&D',
      title: 'Research & Development Spending Growth',
      text: "How much did Apple spend on Research and Development (R&D) in fiscal 2024 compared to 2023?",
    },
  ]

  return (
    <div className="conversation-hero-card">
      <div className="hero-top-badge">
        <span className="hero-badge-dot" />
        SEC Form 10-K Financial Copilot
      </div>

      <h1 className="hero-main-title">
        High-Conviction Financial Analysis With Verbatim Grounding
      </h1>

      <p className="hero-main-subtitle">
        Every factual answer, metric, and percentage is anchored to exact SEC filing passages with clickable citation inspection.
      </p>

      <div className="prompt-cards-grid">
        {suggestedPrompts.map((p, idx) => {
          const Icon = p.icon
          return (
            <button
              key={idx}
              type="button"
              className="prompt-template-card group"
              onClick={() => onSelectPrompt?.(p.text)}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="prompt-card-tag flex items-center gap-1.5">
                  <Icon className="w-3.5 h-3.5 text-cyan-400" />
                  {p.tag}
                </span>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
              </div>
              <h4 className="prompt-card-title">{p.title}</h4>
              <p className="prompt-card-text">{p.text}</p>
            </button>
          )
        })}
      </div>
    </div>
  )
}
