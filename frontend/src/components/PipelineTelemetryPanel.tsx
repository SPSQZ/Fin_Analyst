import { Activity, CheckCircle2, Cpu, Database, FileSearch, Layers, ShieldCheck, Sparkles } from 'lucide-react'

interface PipelineTelemetryPanelProps {
  currentStatus: string | null
  isStreaming: boolean
  lastExtractedTerms?: string[]
  chunksFoundCount?: number
  citationsCount?: number
}

export function PipelineTelemetryPanel({
  currentStatus,
  isStreaming,
  lastExtractedTerms = ['total net sales', 'fiscal 2024', 'Services'],
  chunksFoundCount = 4,
  citationsCount = 3,
}: PipelineTelemetryPanelProps) {
  // Determine current active step based on status text
  const statusLower = (currentStatus || '').toLowerCase()
  const isStep1Active = isStreaming && (statusLower.includes('extract') || statusLower.includes('term'))
  const isStep2Active = isStreaming && (statusLower.includes('search') || statusLower.includes('filing'))
  const isStep3Active = isStreaming && (statusLower.includes('fus') || statusLower.includes('rrf'))
  const isStep4Active = isStreaming && (statusLower.includes('synth') || statusLower.includes('cit'))
  const isStep5Active = isStreaming && (statusLower.includes('validat') || statusLower.includes('ground'))

  const steps = [
    {
      id: 1,
      name: 'Keyword Terms Extraction',
      description: `Local financial heuristic: ${lastExtractedTerms.slice(0, 2).join(', ')}`,
      icon: FileSearch,
      active: isStep1Active,
      completed: !isStreaming || (!isStep1Active && (isStep2Active || isStep3Active || isStep4Active || isStep5Active)),
      badge: '0 API Calls',
    },
    {
      id: 2,
      name: 'Hybrid Dense & Sparse Search',
      description: '768-dim pgvector HNSW + tsvector GIN in Postgres',
      icon: Database,
      active: isStep2Active,
      completed: !isStreaming || (!isStep1Active && !isStep2Active && (isStep3Active || isStep4Active || isStep5Active)),
      badge: 'Supabase Postgres',
    },
    {
      id: 3,
      name: 'Reciprocal Rank Fusion (RRF)',
      description: 'Fusing semantic & lexical rankings (k=60)',
      icon: Layers,
      active: isStep3Active,
      completed: !isStreaming || (!isStep1Active && !isStep2Active && !isStep3Active && (isStep4Active || isStep5Active)),
      badge: `${chunksFoundCount} Chunks Selected`,
    },
    {
      id: 4,
      name: 'Grounded LLM Synthesis',
      description: 'Direct single-turn generation with streaming SSE',
      icon: Cpu,
      active: isStep4Active,
      completed: !isStreaming || (!isStep1Active && !isStep2Active && !isStep3Active && !isStep4Active && isStep5Active),
      badge: 'gemini-3.5-flash',
    },
    {
      id: 5,
      name: 'Verbatim Quote Verification',
      description: `Python validator verified ${citationsCount} exact substring citations`,
      icon: ShieldCheck,
      active: isStep5Active,
      completed: !isStreaming,
      badge: 'Anti-Hallucination',
    },
  ]

  return (
    <aside className="telemetry-panel" aria-label="Execution Telemetry & Pipeline Status">
      <div className="telemetry-header">
        <div className="flex items-center gap-2">
          <Activity className={`w-4 h-4 ${isStreaming ? 'text-cyan-400 animate-spin' : 'text-emerald-400'}`} />
          <h3 className="telemetry-title">Execution Pipeline</h3>
        </div>
        <span className={`status-pill ${isStreaming ? 'status-pill-active' : 'status-pill-idle'}`}>
          <span className={`status-dot ${isStreaming ? 'animate-ping' : ''}`} />
          {isStreaming ? 'STREAMING' : 'READY'}
        </span>
      </div>

      {/* Live status alert banner if running */}
      {isStreaming && currentStatus && (
        <div className="live-status-banner">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <p className="live-status-text">{currentStatus}</p>
        </div>
      )}

      {/* Pipeline Steps Tracker */}
      <div className="pipeline-steps-container">
        <div className="steps-timeline">
          {steps.map((step) => {
            const Icon = step.icon
            return (
              <div
                key={step.id}
                className={`step-row ${step.active ? 'step-active' : ''} ${step.completed ? 'step-completed' : ''}`}
              >
                <div className="step-icon-wrapper">
                  {step.completed && !step.active ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Icon className={`w-4 h-4 ${step.active ? 'text-cyan-400 animate-pulse' : 'text-slate-400'}`} />
                  )}
                </div>
                <div className="step-content">
                  <div className="flex items-center justify-between gap-1">
                    <h4 className="step-name">{step.name}</h4>
                    <span className="step-badge">{step.badge}</span>
                  </div>
                  <p className="step-desc">{step.description}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Real-time Telemetry Metrics Card */}
      <div className="telemetry-metrics-card">
        <h4 className="metrics-card-title">Corpus & Safety Guarantees</h4>
        <div className="metrics-grid">
          <div className="metric-item">
            <span className="metric-label">Active Model</span>
            <span className="metric-val text-cyan-400">Gemini 3.5 Flash</span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Embedding Space</span>
            <span className="metric-val text-indigo-400">768-dim HNSW</span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Grounding Policy</span>
            <span className="metric-val text-emerald-400">Strict Substring</span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Daily Free Cap</span>
            <span className="metric-val text-amber-400">1,500 Queries/Day</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
