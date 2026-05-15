import { ref } from 'vue'
import { sseUrl } from './useApi'
import type { AgentEvent, EventPart } from '@/types'

export function useSSE() {
  const isStreaming = ref(false)
  const error = ref<string | null>(null)

  async function sendMessage(
    appName: string,
    userId: string,
    sessionId: string,
    message: string,
    onEvent: (event: AgentEvent) => void,
  ) {
    isStreaming.value = true
    error.value = null

    try {
      const resp = await fetch(sseUrl('/run_sse'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          app_name: appName,
          user_id: userId,
          session_id: sessionId,
          new_message: { role: 'user', parts: [{ text: message }] },
          streaming: true,
        }),
      })

      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(`Server error ${resp.status}: ${text}`)
      }

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          // Flush remaining bytes from TextDecoder (handles partial UTF-8)
          buffer += decoder.decode()
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const data = line.substring(5).trim()
          if (!data) continue

          try {
            const event: AgentEvent = JSON.parse(data)
            onEvent(event)
          } catch {
            // skip unparseable lines
          }
        }
      }

      // Process any remaining buffered data after stream ends
      if (buffer.startsWith('data:')) {
        const data = buffer.substring(5).trim()
        if (data) {
          try {
            const event: AgentEvent = JSON.parse(data)
            onEvent(event)
          } catch { /* skip */ }
        }
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      isStreaming.value = false
    }
  }

  return { isStreaming, error, sendMessage }
}
