/**
 * Bunny Stream's player is an iframe; its player.js bridge reports the playhead so we can
 * resume where the learner left off and count real watch time.
 * https://docs.bunny.net/docs/playback-control-api
 */
type Handler = (data?: { seconds?: number; duration?: number }) => void
export interface BunnyPlayer {
  on(event: 'ready' | 'play' | 'pause' | 'ended' | 'timeupdate', fn: Handler): void
  off(event: string): void
  setCurrentTime(sec: number): void
  supports(kind: 'method' | 'event', name: string): boolean
}
declare global {
  interface Window {
    playerjs?: { Player: new (el: HTMLIFrameElement) => BunnyPlayer }
  }
}

const SRC = 'https://assets.mediadelivery.net/playerjs/playerjs-latest.min.js'
let loading: Promise<void> | null = null

/** Loads player.js once, on the first video only (it is never in the main bundle). */
export function loadPlayerJs(): Promise<void> {
  if (window.playerjs) return Promise.resolve()
  loading ??= new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SRC
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => {
      loading = null
      reject(new Error('player.js failed to load'))
    }
    document.head.appendChild(s)
  })
  return loading
}

/** The embed URL with resume time and the options we want (keeps the signed token). */
export function embedUrl(url: string, startSec: number) {
  const u = new URL(url)
  u.searchParams.set('autoplay', 'false')
  u.searchParams.set('preload', 'true')
  u.searchParams.set('responsive', 'true')
  if (startSec > 5) u.searchParams.set('t', String(Math.floor(startSec)))
  return u.toString()
}

/** Where the current video is, so a note can be pinned to that moment. */
export const playhead = { key: '', sec: 0 }
