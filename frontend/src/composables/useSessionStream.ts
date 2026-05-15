import { onUnmounted, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { sseUrl } from './useApi'

export interface SessionStreamEvent {
  agent: string
  text: string
  timestamp: number
}

/**
 * Long-lived SSE connection for out-of-band AI responses on a session
 * (scheduled reminders, heartbeat broadcasts, agent-to-agent calls).
 *
 * The backend publishes AGENT_RESPONSE bus events for every AI reply —
 * both /run_sse triggered and schedule_service triggered. This stream
 * delivers them so the web UI sees scheduled fires without needing a
 * request-bound connection to be kept open.
 */
export function useSessionStream(
  sessionIdRef: Ref<string | null>,
  onEvent: (ev: SessionStreamEvent) => void,
) {
  const connected = ref(false)
  let es: EventSource | null = null

  function close() {
    if (es) {
      es.close()
      es = null
      connected.value = false
    }
  }

  function open(sessionId: string) {
    close()
    es = new EventSource(sseUrl(`/sessions/${sessionId}/events/stream`))
    es.onopen = () => { connected.value = true }
    es.onerror = () => { connected.value = false }
    es.onmessage = (e) => {
      try {
        const data: SessionStreamEvent = JSON.parse(e.data)
        onEvent(data)
      } catch {
        // skip unparseable lines
      }
    }
  }

  watch(sessionIdRef, (id) => {
    if (id) open(id)
    else close()
  }, { immediate: true })

  onUnmounted(close)

  return { connected }
}
