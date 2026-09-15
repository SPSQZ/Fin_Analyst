function requireEnv(name: string, value: string | undefined): string {
  const normalizedValue = value?.trim()

  if (!normalizedValue) {
    throw new Error(`Missing required environment variable: ${name}`)
  }

  return normalizedValue
}

function requireUrl(name: string, value: string | undefined): string {
  const normalizedValue = requireEnv(name, value)

  try {
    return new URL(normalizedValue).toString().replace(/\/$/, '')
  } catch {
    throw new Error(`Environment variable ${name} must be a valid URL`)
  }
}

export const env = {
  apiBaseUrl: requireUrl('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL),
  supabaseUrl: requireUrl('VITE_SUPABASE_URL', import.meta.env.VITE_SUPABASE_URL),
  supabaseAnonKey: requireEnv(
    'VITE_SUPABASE_ANON_KEY',
    import.meta.env.VITE_SUPABASE_ANON_KEY,
  ),
} as const