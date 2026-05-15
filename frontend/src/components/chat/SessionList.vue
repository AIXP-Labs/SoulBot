<script setup lang="ts">
import { useSessionStore } from '@/stores/session'
import { useAgentStore } from '@/stores/agent'
import type { Session } from '@/types'

const sessionStore = useSessionStore()
const agentStore = useAgentStore()

function formatTime(ts: number | null): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

function selectSession(session: Session) {
  sessionStore.selectSession(session.id)
}

async function createNew() {
  if (agentStore.currentAgent) {
    await sessionStore.createSession(agentStore.currentAgent)
  }
}

async function deleteSession(sessionId: string) {
  if (agentStore.currentAgent) {
    await sessionStore.deleteSession(agentStore.currentAgent, sessionId)
  }
}

function sessionTitle(s: Session): string {
  return s.title || s.id.substring(0, 8)
}
</script>

<template>
  <div class="session-list">
    <div class="session-header">
      <span class="session-label">Sessions</span>
      <button class="btn-new" @click="createNew" title="New session">+</button>
    </div>
    <div class="session-items">
      <div
        v-for="s in sessionStore.sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === sessionStore.currentSessionId }"
        @click="selectSession(s)"
      >
        <div class="session-info">
          <span class="session-title">{{ sessionTitle(s) }}</span>
          <span class="session-time">{{ formatTime(s.last_update_time || s.created_at) }}</span>
        </div>
        <button class="del-btn" @click.stop="deleteSession(s.id)" title="Delete">&times;</button>
      </div>
      <div v-if="sessionStore.sessions.length === 0" class="session-empty">
        No sessions yet
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-bottom: 1px solid var(--border);
}

.session-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.btn-new {
  background: var(--bg-card);
  color: var(--accent);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  width: 24px;
  height: 24px;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.btn-new:hover { background: var(--border); }

.session-items {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.session-item {
  padding: 8px 10px;
  margin: 2px 0;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.session-item:hover { background: var(--bg-card); }
.session-item.active { background: var(--user-bg); color: var(--text); }

.session-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.session-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  font-size: 10px;
  opacity: 0.7;
}

.del-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
  flex-shrink: 0;
  line-height: 1;
}
.del-btn:hover { color: var(--error); }

.session-empty {
  padding: 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}
</style>
