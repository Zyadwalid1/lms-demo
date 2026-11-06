/** Only same-site paths are followed after sign-in (no open redirects). */
export function safeNext(v: string | null) {
  return v && v.startsWith('/') && !v.startsWith('//') ? v : '/learn'
}
