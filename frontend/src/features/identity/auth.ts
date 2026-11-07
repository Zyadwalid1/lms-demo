/** Sign-in through django-allauth's headless API (browser client: session cookie + CSRF).
 * https://docs.allauth.org/en/latest/headless/openapi-specification/ */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, csrfToken, unwrap } from '@/api/client'
import { forgetInvite } from '@/lib/next'

const BASE = '/_allauth/browser/v1'

type AllauthResponse = {
  status: number
  data?: Record<string, unknown> & { flows?: { id: string; is_pending?: boolean }[] }
  meta?: { is_authenticated?: boolean }
  errors?: { message: string; code: string; param?: string }[]
}

async function call(method: string, path: string, body?: unknown): Promise<AllauthResponse> {
  const res = await fetch(BASE + path, {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
    body: body ? JSON.stringify(body) : undefined,
  })
  const json = (await res.json().catch(() => ({ status: res.status }))) as AllauthResponse
  return { ...json, status: res.status }
}

export type Me = Awaited<ReturnType<typeof fetchMe>>
const fetchMe = () => unwrap(api.GET('/api/v1/identity/me'))

/** The signed-in person (with their company memberships), or null for visitors. */
export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await fetchMe()
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    staleTime: 5 * 60_000,
  })
}

export function useAuthConfig() {
  return useQuery({
    queryKey: ['auth-config'],
    queryFn: async () => (await call('GET', '/config')).data as { socialaccount?: { providers: { id: string; name: string }[] } },
    staleTime: Infinity,
  })
}

export class AuthError extends Error {
  fields: Record<string, string>
  pendingVerification: boolean
  constructor(message: string, fields: Record<string, string> = {}, pendingVerification = false) {
    super(message)
    this.fields = fields
    this.pendingVerification = pendingVerification
  }
}

function raise(r: AllauthResponse): never {
  const fields: Record<string, string> = {}
  for (const e of r.errors ?? []) if (e.param) fields[e.param] = e.message
  const pending = r.status === 401 && !!r.data?.flows?.some((f) => f.id === 'verify_email' && f.is_pending)
  throw new AuthError(
    pending ? 'Check your inbox: confirm your email address to finish signing in.' : (r.errors?.[0]?.message ?? 'Something went wrong. Please try again.'),
    fields,
    pending,
  )
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { email: string; password: string }) => {
      const r = await call('POST', '/auth/login', v)
      if (r.status !== 200) raise(r)
    },
    // refetch even when no screen is showing the user yet (the sign-in page), so the
    // next page already knows who is signed in
    onSuccess: () => qc.refetchQueries({ queryKey: ['me'], type: 'all' }),
  })
}

export function useSignup() {
  return useMutation({
    mutationFn: async (v: { email: string; password: string }) => {
      const r = await call('POST', '/auth/signup', v)
      if (r.status === 200) return 'signed-in'
      if (r.status === 401 && r.data?.flows?.some((f) => f.id === 'verify_email')) return 'verify-email'
      raise(r)
    },
  })
}

export function useVerifyEmail() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (key: string) => {
      const r = await call('POST', '/auth/email/verify', { key })
      if (r.status !== 200 && r.status !== 401) raise(r)
      return r.status === 200
    },
    // refetch even when no screen is showing the user yet (the sign-in page), so the
    // next page already knows who is signed in
    onSuccess: () => qc.refetchQueries({ queryKey: ['me'], type: 'all' }),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => call('DELETE', '/auth/session'),
    onSettled: () => {
      // an invitation waiting in this browser belongs to whoever was signed in
      forgetInvite()
      qc.clear()
      void qc.invalidateQueries()
    },
  })
}

/** Google / Microsoft: allauth expects a real form POST so the browser follows the redirect. */
export function providerRedirect(provider: string, next = '/') {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = `${BASE}/auth/provider/redirect`
  const fields = { provider, process: 'login', callback_url: `${location.origin}/account/provider/callback?next=${encodeURIComponent(next)}`, csrfmiddlewaretoken: csrfToken() }
  for (const [name, value] of Object.entries(fields)) {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = name
    input.value = value
    form.appendChild(input)
  }
  document.body.appendChild(form)
  form.submit()
}

/** Whether the account has a password yet (people who joined with Google or Microsoft may not). */
export function useHasPassword() {
  return useQuery({
    queryKey: ['has-password'],
    queryFn: async () => {
      const r = await call('GET', '/auth/session')
      return (r.data?.user as { has_usable_password?: boolean } | undefined)?.has_usable_password ?? true
    },
    staleTime: 5 * 60_000,
  })
}

export function useChangePassword() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { current_password?: string; new_password: string }) => {
      const r = await call('POST', '/account/password/change', v)
      if (r.status !== 200) raise(r)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['has-password'] }),
  })
}

export function useUpdateMe() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { full_name?: string | null; timezone?: string | null; preferred_currency?: string | null }) => unwrap(api.PATCH('/api/v1/identity/me', { body })),
    onSuccess: (me) => qc.setQueryData(['me'], me),
  })
}
