/** Which space the user is working in: their own learning (null) or a company (org id).
 * The API client sends it as X-Org-Id; the server checks membership every time. */
const KEY = 'orgId'

export function currentOrgId(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function setCurrentOrgId(id: string | null) {
  try {
    if (id) localStorage.setItem(KEY, id)
    else localStorage.removeItem(KEY)
  } catch {
    /* private mode: falls back to personal space */
  }
}
