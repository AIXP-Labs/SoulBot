<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { useSessionStore } from '@/stores/session'
import { apiDelete } from '@/composables/useApi'
import type { Session } from '@/types'

const agentStore = useAgentStore()
const sessionStore = useSessionStore()
const loading = ref(true)
const selectedIds = ref<string[]>([])

onMounted(async () => {
  await agentStore.loadAgents()
  if (agentStore.currentAgent) {
    await sessionStore.loadSessions(agentStore.currentAgent)
  }
  loading.value = false
})

function formatDate(ts: number | null): string {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
}

function isSelected(id: string): boolean {
  return selectedIds.value.includes(id)
}

function toggleSelect(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function toggleAll() {
  if (selectedIds.value.length === sessionStore.sessions.length) {
    selectedIds.value = []
  } else {
    selectedIds.value = sessionStore.sessions.map(s => s.id)
  }
}

async function deleteSelected() {
  if (!agentStore.currentAgent) return
  const ids = [...selectedIds.value]
  for (const id of ids) {
    await apiDelete(`/apps/${agentStore.currentAgent}/users/default/sessions/${id}`)
  }
  selectedIds.value = []
  await sessionStore.loadSessions(agentStore.currentAgent)
}

function sessionTitle(s: Session): string {
  return s.title || s.id.substring(0, 12)
}
</script>

<template>
  <div class="sessions-page">
    <div class="page-header">
      <h2>Sessions</h2>
      <span class="badge">{{ sessionStore.sessions.length }}</span>
      <div class="header-actions" v-if="selectedIds.length > 0">
        <span class="selected-count">{{ selectedIds.length }} selected</span>
        <button class="btn-delete" @click="deleteSelected">Delete Selected</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading sessions...</div>

    <div v-else-if="sessionStore.sessions.length === 0" class="empty">No sessions</div>

    <div v-else class="sessions-table-wrap">
      <table class="sessions-table">
        <thead>
          <tr>
            <th class="col-check">
              <input type="checkbox" @change="toggleAll" :checked="selectedIds.length === sessionStore.sessions.length && sessionStore.sessions.length > 0" />
            </th>
            <th>Title</th>
            <th>Session ID</th>
            <th>Last Agent</th>
            <th>Created</th>
            <th>Last Updated</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sessionStore.sessions" :key="s.id" :class="{ selected: isSelected(s.id) }">
            <td class="col-check">
              <input type="checkbox" :checked="isSelected(s.id)" @change="toggleSelect(s.id)" />
            </td>
            <td>{{ sessionTitle(s) }}</td>
            <td class="cell-id">{{ s.id.substring(0, 12) }}...</td>
            <td>{{ s.last_agent || '—' }}</td>
            <td>{{ formatDate(s.created_at) }}</td>
            <td>{{ formatDate(s.last_update_time) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.sessions-page {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-count {
  font-size: 12px;
  color: var(--text-muted);
}

.btn-delete {
  background: var(--error);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
}
.btn-delete:hover { opacity: 0.9; }

.loading, .empty {
  color: var(--text-muted);
  padding: 40px;
  text-align: center;
}

.sessions-table-wrap {
  overflow-x: auto;
}

.sessions-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.sessions-table th,
.sessions-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.sessions-table th {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  background: var(--bg-card);
}

.sessions-table tr:hover td {
  background: var(--accent-bg);
}

.sessions-table tr.selected td {
  background: var(--accent-bg);
}

.col-check {
  width: 40px;
  text-align: center;
}

.cell-id {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--accent);
}
</style>
