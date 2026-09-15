import { AlertCircle, AlertTriangle, LogIn, RefreshCw, ShieldAlert, WifiOff, X } from 'lucide-react'
import { supabase } from '../lib/supabase'

interface ErrorAlertProps {
  error: string
  errorType?: 'auth-expired' | 'retrieval-failure' | 'grounding-failure' | 'network-cors' | 'provider-unavailable' | 'general'
  onRetry?: () => void
  onDismiss?: () => void
}

export function ErrorAlert({ error, errorType, onRetry, onDismiss }: ErrorAlertProps) {
  // Infer error type if not explicitly provided
  const resolvedType = errorType || (() => {
    const lower = error.toLowerCase()
    if (lower.includes('401') || lower.includes('auth') || lower.includes('session') || lower.includes('token')) {
      return 'auth-expired'
    }
    if (lower.includes('network') || lower.includes('cors') || lower.includes('fetch') || lower.includes('http 0')) {
      return 'network-cors'
    }
    if (lower.includes('grounding') || lower.includes('hallucin') || lower.includes('unsupported claim')) {
      return 'grounding-failure'
    }
    if (lower.includes('retriev') || lower.includes('no chunk') || lower.includes('filing not found')) {
      return 'retrieval-failure'
    }
    if (lower.includes('503') || lower.includes('unavailable') || lower.includes('overload') || lower.includes('rate limit') || lower.includes('traffic')) {
      return 'provider-unavailable'
    }
    return 'general'
  })()

  const handleSignOut = () => {
    void supabase.auth.signOut().then(() => {
      window.location.href = '/login'
    })
  }

  const getIcon = () => {
    switch (resolvedType) {
      case 'auth-expired':
        return <LogIn className="w-4 h-4 text-amber-400" />
      case 'network-cors':
        return <WifiOff className="w-4 h-4 text-red-400" />
      case 'grounding-failure':
        return <ShieldAlert className="w-4 h-4 text-emerald-400" />
      case 'provider-unavailable':
        return <AlertTriangle className="w-4 h-4 text-amber-400" />
      default:
        return <AlertCircle className="w-4 h-4 text-red-400" />
    }
  }

  const getTitle = () => {
    switch (resolvedType) {
      case 'auth-expired':
        return 'Session Expired (401)'
      case 'network-cors':
        return 'Network / Connection Error'
      case 'grounding-failure':
        return 'Strict Grounding Shield Activated'
      case 'retrieval-failure':
        return 'Retrieval Failure'
      case 'provider-unavailable':
        return 'AI Provider Capacity Notice'
      default:
        return 'Request Error'
    }
  }

  return (
    <div className={`alert-banner-box alert-type-${resolvedType}`} role="alert">
      <div className="alert-content-wrap">
        <div className="flex items-center gap-2 mb-1">
          {getIcon()}
          <strong className="text-sm font-semibold">{getTitle()}</strong>
        </div>
        <p className="text-xs text-slate-300 mb-2 leading-relaxed">{error}</p>

        <div className="flex items-center gap-2">
          {onRetry && (
            <button type="button" className="alert-btn-action" onClick={onRetry}>
              <RefreshCw className="w-3 h-3" />
              <span>Retry</span>
            </button>
          )}
          {resolvedType === 'auth-expired' && (
            <button type="button" className="alert-btn-action" onClick={handleSignOut}>
              <span>Re-authenticate</span>
            </button>
          )}
          {onDismiss && (
            <button type="button" className="alert-btn-dismiss" onClick={onDismiss}>
              <span>Dismiss</span>
            </button>
          )}
        </div>
      </div>
      {onDismiss && (
        <button type="button" className="alert-close-btn" onClick={onDismiss} aria-label="Dismiss alert">
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  )
}
