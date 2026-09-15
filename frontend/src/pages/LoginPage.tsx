import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { supabase } from '../lib/supabase'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    const { error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    setSubmitting(false)

    if (signInError) {
      setError(signInError.message)
      return
    }

    const from = (location.state as { from?: { pathname?: string } } | null)?.from
      ?.pathname
    navigate(from ?? '/', { replace: true })
  }

  return (
    <main className="auth-layout">
      <section className="auth-intro">
        <p className="eyebrow">Document Copilot</p>
        <h1>Read the filing. Find the signal.</h1>
        <p>Search annual reports and trace every answer back to its source.</p>
      </section>
      <section className="auth-panel">
        <p className="eyebrow">Welcome back</p>
        <h2>Sign in</h2>
        <form onSubmit={handleSubmit}>
          <label>
            Email
            <input
              required
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              required
              minLength={6}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button disabled={submitting} type="submit">
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <p className="form-footer">
          New here? <Link to="/signup">Create an account</Link>
        </p>
      </section>
    </main>
  )
}