import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, apiPost, apiDelete } from '@/composables/useApi'
import type { Session, SessionDetail } from '@/types'

const USER_ID = 'default'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(localStorage.getItem('soulbot:lastSession'))
  const currentApp = ref<string | null>(null)

  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value) ?? null
  )

  async function loadSessions(appName: string) {
    currentApp.value = appName
    // Plan 18 / 01: detect agent switch (within same CLI) to clear stale
    // session pointer — different agents sharing the same cli_name partition
    // would otherwise leak conversation history across agents.
    const storedAgent = localStorage.getItem('soulbot:lastAgent') || ''
    if (storedAgent && storedAgent !== appName) {
      currentSessionId.value = null
      localStorage.removeItem('soulbot:lastSession')
    }
    if (appName) {
      localStorage.setItem('soulbot:lastAgent', appName)
    }
    // Detect CLI provider change (e.g. switched from claude_cli → codex_cli
    // via .env): sessions are partitioned per cli_name on the backend, so a
    // stale lastSession id from the previous provider is invalid. Clear it
    // to avoid showing "no such session" + force a fresh provider context.
    try {
      const info = await api<{ cli_name: string }>('/cli-info')
      const currentCli = info.cli_name || ''
      const storedCli = localStorage.getItem('soulbot:lastCli') || ''
      if (storedCli && storedCli !== currentCli) {
        // Provider switched — clear stale session reference
        currentSessionId.value = null
        localStorage.removeItem('soulbot:lastSession')
      }
      if (currentCli) {
        localStorage.setItem('soulbot:lastCli', currentCli)
      }
    } catch {
      // /cli-info unavailable — best-effort, skip
    }

    sessions.value = await api<Session[]>(
      `/apps/${appName}/users/${USER_ID}/sessions`
    )
    // Validate restored session; fallback to first
    if (currentSessionId.value && !sessions.value.find(s => s.id === currentSessionId.value)) {
      selectSession(null)
    }
    if (!currentSessionId.value && sessions.value.length > 0) {
      selectSession(sessions.value[0]?.id ?? null)
    }
    // Auto-create a session when the list is empty so the user can chat immediately
    if (sessions.value.length === 0) {
      await createSession(appName)
    }
  }

  async function createSession(appName: string): Promise<Session> {
    const session = await apiPost<Session>(
      `/apps/${appName}/users/${USER_ID}/sessions`,
      {}
    )
    selectSession(session.id)
    await loadSessions(appName)
    return session
  }

  async function deleteSession(appName: string, sessionId: string) {
    await apiDelete(`/apps/${appName}/users/${USER_ID}/sessions/${sessionId}`)
    if (currentSessionId.value === sessionId) {
      selectSession(null)
    }
    await loadSessions(appName)
  }

  async function getSessionDetail(appName: string, sessionId: string): Promise<SessionDetail> {
    return api<SessionDetail>(
      `/apps/${appName}/users/${USER_ID}/sessions/${sessionId}`
    )
  }

  function selectSession(sessionId: string | null) {
    currentSessionId.value = sessionId
    if (sessionId) {
      localStorage.setItem('soulbot:lastSession', sessionId)
    } else {
      localStorage.removeItem('soulbot:lastSession')
    }
  }

  return {
    sessions,
    currentSessionId,
    currentApp,
    currentSession,
    loadSessions,
    createSession,
    deleteSession,
    getSessionDetail,
    selectSession,
  }
})
