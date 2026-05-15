<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, apiPost } from '@/composables/useApi'
import type {
  AgentMessageEntry,
  AgentMessageListResponse,
} from '@/types'
import { ALL_MESSAGE_STATUSES } from '@/types'

const messages = ref<AgentMessageEntry[]>([])
const loading = ref(true)
const errorMsg = ref('')
const expandedIds = ref<Set<string>>(new Set())
const cancellingIds = ref<Set<string>>(new Set())
const statusFilter = ref<string>('')
const limitFilter = ref<number>(30)

const filteredMessages = computed(() => {
  if (!statusFilter.value) return messages.value
  return messages.value.filter((m) => m.status === statusFilter.value)
})

onMounted(async () => {
  await loadMessages()
})

async function loadMessages() {
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await api<AgentMessageListResponse | AgentMessageEntry[]>(
      `/message/list?limit=${limitFilter.value}`,
    )
    // Backend returns {entries, count}; tolerate plain array as well
    messages.value = Array.isArray(resp)
      ? resp
      : (resp?.entries ?? [])
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('404')) {
      errorMsg.value = 'Message service not available (no message_service configured)'
    } else {
      errorMsg.value = e instanceof Error ? e.message : String(e)
    }
    messages.value = []
  } finally {
    loading.value = false
  }
}

function toggleExpand(id: string) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
  // Trigger reactivity
  expandedIds.value = new Set(expandedIds.value)
}

function isCancellable(m: AgentMessageEntry): boolean {
  return m.status === 'pending' || m.status === 'processing'
}

async function cancelMessage(id: string) {
  if (!window.confirm(`Cancel message ${id}?`)) return
  cancellingIds.value.add(id)
  try {
    await apiPost(`/message/${encodeURIComponent(id)}/cancel`, {})
    await loadMessages()
  } catch (e: unknown) {
    window.alert(`Failed to cancel: ${e instanceof Error ? e.message : String(e)}`)
  } finally {
    cancellingIds.value.delete(id)
    cancellingIds.value = new Set(cancellingIds.value)
  }
}

function statusBadge(status: string): string {
  switch (status) {
    case 'pending': return 'badge--warning'
    case 'processing': return 'badge--warning'
    case 'delivered': return 'badge--success'
    case 'failed': return 'badge--error'
    case 'cancelled': return ''
    default: return ''
  }
}

function formatDate(ts: string | null): string {
  if (!ts) return '—'
  return new Date(ts).toLocaleString()
}

function shortId(id: string): string {
  return id.length > 16 ? id.slice(0, 16) + '…' : id
}

watch(limitFilter, () => {
  loadMessages()
})

function jumpToParent(parentId: string) {
  // Expand the parent row and scroll into view
  expandedIds.value.add(parentId)
  expandedIds.value = new Set(expandedIds.value)
  setTimeout(() => {
    const el = document.getElementById(`msg-row-${parentId}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 50)
}
</script>

<template>
  <div class="messages-page">
    <div class="page-header">
      <h2>Agent Messages</h2>
      <span class="badge">{{ messages.length }}</span>

      <select
        v-model="statusFilter"
        class="filter-select"
        aria-label="Filter messages by status"
      >
        <option value="">All statuses</option>
        <option v-for="s in ALL_MESSAGE_STATUSES" :key="s" :value="s">
          {{ s.charAt(0).toUpperCase() + s.slice(1) }}
        </option>
      </select>

      <button
        class="btn-refresh"
        :disabled="cancellingIds.size > 0"
        :title="cancellingIds.size > 0 ? 'Cancel in flight; refresh disabled' : ''"
        @click="loadMessages"
      >
        Refresh
      </button>

      <label class="limit-input">
        Show
        <input
          type="number"
          v-model.number="limitFilter"
          min="1"
          max="1000"
          class="limit-number"
        />
        messages
      </label>
    </div>

    <div v-if="loading" class="loading">Loading messages...</div>
    <div v-else-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
    <div v-else-if="filteredMessages.length === 0" class="empty">
      No agent messages
    </div>

    <div v-else class="msg-table-wrap">
      <table class="msg-table">
        <thead>
          <tr>
            <th></th>
            <th>ID</th>
            <th>From → To</th>
            <th>Status</th>
            <th>Mode</th>
            <th>Depth</th>
            <th>Created</th>
            <th>Delivered</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="m in filteredMessages" :key="m.id">
            <tr
              :id="`msg-row-${m.id}`"
              class="msg-row"
              :class="{ 'msg-row--expanded': expandedIds.has(m.id) }"
              :tabindex="0"
              role="button"
              :aria-expanded="expandedIds.has(m.id)"
              :aria-label="`Toggle details for message ${m.id}`"
              @click="toggleExpand(m.id)"
              @keydown.enter.prevent="toggleExpand(m.id)"
              @keydown.space.prevent="toggleExpand(m.id)"
            >
              <td class="cell-toggle">
                <span class="caret" aria-hidden="true">
                  {{ expandedIds.has(m.id) ? '▼' : '▶' }}
                </span>
              </td>
              <td class="cell-id" :title="m.id">{{ shortId(m.id) }}</td>
              <td>
                <span class="agent-tag">{{ m.from_agent }}</span>
                <span class="arrow"> → </span>
                <span class="agent-tag">{{ m.to_agent }}</span>
              </td>
              <td>
                <span class="badge" :class="statusBadge(m.status)">
                  {{ m.status }}
                </span>
              </td>
              <td>
                <span class="mode-tag" :class="`mode--${m.reply_mode}`">
                  {{ m.reply_mode }}
                </span>
              </td>
              <td class="cell-num">{{ m.depth }}</td>
              <td class="cell-date">{{ formatDate(m.created_at) }}</td>
              <td class="cell-date">{{ formatDate(m.delivered_at) }}</td>
              <td @click.stop @keydown.stop>
                <button
                  v-if="isCancellable(m)"
                  class="btn-cancel"
                  :disabled="cancellingIds.has(m.id)"
                  :aria-label="`Cancel message ${m.id}`"
                  @click="cancelMessage(m.id)"
                >
                  {{ cancellingIds.has(m.id) ? '...' : 'Cancel' }}
                </button>
                <span v-else class="muted">—</span>
              </td>
            </tr>
            <tr v-if="expandedIds.has(m.id)" class="msg-detail-row">
              <td colspan="9">
                <div class="msg-detail">
                  <div class="meta-grid">
                    <div><span class="meta-key">ID</span><code>{{ m.id }}</code></div>
                    <div>
                      <span class="meta-key">Parent</span>
                      <a
                        v-if="m.parent_id"
                        href="#"
                        class="link"
                        @click.prevent="jumpToParent(m.parent_id!)"
                      >
                        {{ m.parent_id }}
                      </a>
                      <span v-else class="muted">—</span>
                    </div>
                    <div><span class="meta-key">Created</span>{{ formatDate(m.created_at) }}</div>
                    <div><span class="meta-key">Delivered</span>{{ formatDate(m.delivered_at) }}</div>
                  </div>

                  <details class="sub-block" open>
                    <summary>AISOP payload</summary>
                    <!-- XSS safe: Vue mustache auto-escapes HTML in text;
                         JSON.stringify produces plaintext, never markup. -->
                    <pre class="codeblock">{{ JSON.stringify(m.aisop, null, 2) }}</pre>
                  </details>

                  <details v-if="m.result" class="sub-block">
                    <summary>Result</summary>
                    <pre class="codeblock">{{ m.result }}</pre>
                  </details>

                  <details v-if="m.error" class="sub-block sub-block--error">
                    <summary>Error</summary>
                    <pre class="codeblock">{{ m.error }}</pre>
                  </details>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.messages-page {
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

.filter-select {
  margin-left: 8px;
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.btn-refresh {
  margin-left: auto;
  background: var(--bg-card);
  color: var(--accent);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
}
.btn-refresh:hover { background: var(--border); }

.limit-input {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
  margin-left: 8px;
}

.limit-number {
  width: 60px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-card);
  color: var(--text);
  font-family: inherit;
}

.btn-cancel {
  background: transparent;
  color: var(--error);
  border: 1px solid var(--error);
  border-radius: var(--radius-sm);
  padding: 2px 10px;
  font-size: 11px;
  cursor: pointer;
}
.btn-cancel:hover:not(:disabled) { background: var(--error); color: #fff; }
.btn-cancel:disabled { opacity: 0.5; cursor: wait; }

.loading, .empty {
  color: var(--text-muted);
  padding: 40px;
  text-align: center;
}

.error-msg {
  color: var(--error);
  padding: 16px;
  background: #2a1a1a;
  border-radius: var(--radius);
  font-size: 13px;
}

.msg-table-wrap {
  overflow-x: auto;
}

.msg-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.msg-table th,
.msg-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.msg-table th {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  background: var(--bg-card);
}

.msg-row {
  cursor: pointer;
}
.msg-row:hover td {
  background: var(--accent-bg);
}
.msg-row--expanded td {
  background: var(--accent-bg);
}
/* F4.1 audit fix (v1.8): keyboard focus indicator for accessibility */
.msg-row:focus {
  outline: none;
}
.msg-row:focus td:first-child {
  box-shadow: inset 3px 0 0 var(--accent);
}
.msg-row:focus-visible td {
  background: var(--accent-bg);
}

.cell-toggle {
  width: 24px;
  text-align: center;
}

.caret {
  display: inline-block;
  font-size: 10px;
  color: var(--text-muted);
  width: 12px;
}

.cell-id {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--accent);
}

.cell-date {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.cell-num {
  text-align: right;
  font-family: var(--mono);
  width: 60px;
}

.agent-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-card);
  font-family: var(--mono);
  font-size: 12px;
}

.arrow {
  color: var(--text-muted);
  margin: 0 4px;
}

.mode-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  font-family: var(--mono);
}
.mode--callback {
  border-color: var(--accent);
  color: var(--accent);
}

.muted {
  color: var(--text-muted);
}

.msg-detail-row td {
  background: var(--bg);
  padding: 0;
  border-bottom: 1px solid var(--border);
}

.msg-detail {
  padding: 16px 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(200px, 1fr));
  gap: 6px 24px;
  font-size: 12px;
}

.meta-grid > div {
  display: flex;
  gap: 6px;
  align-items: baseline;
}

.meta-key {
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  min-width: 80px;
}

.meta-grid code {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--accent);
}

.link {
  color: var(--accent);
  text-decoration: none;
  font-family: var(--mono);
  font-size: 12px;
}
.link:hover { text-decoration: underline; }

.sub-block {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0;
  background: var(--bg-card);
}
.sub-block summary {
  cursor: pointer;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--text-muted);
  user-select: none;
}
.sub-block[open] summary {
  border-bottom: 1px solid var(--border);
  color: var(--text);
}
.sub-block--error summary {
  color: var(--error);
}

.codeblock {
  margin: 0;
  padding: 12px;
  font-family: var(--mono);
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
  background: var(--bg);
  color: var(--text);
}
</style>
