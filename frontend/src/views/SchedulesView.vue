<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, apiPost } from '@/composables/useApi'
import type { ScheduleEntry } from '@/types'

const schedules = ref<ScheduleEntry[]>([])
const loading = ref(true)
const errorMsg = ref('')
const expandedIds = ref<Set<string>>(new Set())
const cancellingIds = ref<Set<string>>(new Set())

onMounted(async () => {
  await loadSchedules()
})

async function loadSchedules() {
  loading.value = true
  errorMsg.value = ''
  try {
    // Backend (schedule_service.list) returns {entries, count}.
    // Accept both shapes — wrapped dict or direct array — for resilience.
    const resp = await api<{ entries: ScheduleEntry[]; count: number } | ScheduleEntry[]>(
      '/schedule/list',
    )
    const raw = Array.isArray(resp) ? resp : (resp?.entries ?? [])
    schedules.value = sortSchedules(raw)
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('404')) {
      errorMsg.value = 'Schedule service not available (no schedule_service configured)'
    } else {
      errorMsg.value = e instanceof Error ? e.message : String(e)
    }
    schedules.value = []
  } finally {
    loading.value = false
  }
}

// Best-effort next-fire time computation (client-side). Returns a millisecond
// timestamp; Infinity if we can't determine (sorted to the end).
function computeNextFire(s: ScheduleEntry): number {
  const tc = s.trigger_config
  if (!tc) return Infinity

  // once + run_at → absolute time
  if (tc.type === 'once' && tc.run_at) {
    return new Date(tc.run_at).getTime()
  }
  // once + delay → created_at + delay seconds
  if (tc.type === 'once' && tc.delay !== undefined) {
    const created = s.created_at ? new Date(s.created_at).getTime() : 0
    return created + tc.delay * 1000
  }
  // cron with hour/minute → next daily occurrence
  if (tc.hour !== undefined && tc.minute !== undefined) {
    const now = new Date()
    const next = new Date()
    next.setHours(tc.hour, tc.minute, 0, 0)
    if (next.getTime() <= now.getTime()) {
      next.setDate(next.getDate() + 1)
    }
    return next.getTime()
  }
  // interval trigger → last_run (or created_at) + interval
  if (tc.interval !== undefined) {
    const base = s.last_run
      ? new Date(s.last_run).getTime()
      : s.created_at
        ? new Date(s.created_at).getTime()
        : 0
    return base + tc.interval * 1000
  }
  return Infinity
}

function sortSchedules(list: ScheduleEntry[]): ScheduleEntry[] {
  // Group: active (incl. paused) first; completed next; others (error etc.) last.
  const active: ScheduleEntry[] = []
  const completed: ScheduleEntry[] = []
  const other: ScheduleEntry[] = []
  for (const s of list) {
    if (s.status === 'active' || s.status === 'paused') active.push(s)
    else if (s.status === 'completed') completed.push(s)
    else other.push(s)
  }
  // Active: soonest upcoming fire first (ASC by next_fire)
  active.sort((a, b) => computeNextFire(a) - computeNextFire(b))
  // Completed: most recent run first (DESC by last_run)
  completed.sort((a, b) => {
    const aTime = a.last_run ? new Date(a.last_run).getTime() : 0
    const bTime = b.last_run ? new Date(b.last_run).getTime() : 0
    return bTime - aTime
  })
  // Others (error, unknown) keep original order at the end
  return [...active, ...completed, ...other]
}

function toggleExpand(id: string) {
  const next = new Set(expandedIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedIds.value = next
}

// Heartbeat seeds (hb_*) represent agent lifecycle and are not user-cancellable.
function isCancellable(s: ScheduleEntry): boolean {
  if (s.id.startsWith('hb_')) return false
  return s.status === 'active' || s.status === 'paused'
}

async function cancelSchedule(s: ScheduleEntry, event: MouseEvent) {
  event.stopPropagation()  // prevent row expand toggle
  if (!isCancellable(s)) return
  const ok = window.confirm(
    `Cancel scheduled task "${s.id}"?\n\n` +
    `This will stop future triggers. The record will be kept with status=completed ` +
    `for audit purposes.`,
  )
  if (!ok) return

  cancellingIds.value.add(s.id)
  try {
    await apiPost(`/schedule/${encodeURIComponent(s.id)}/cancel`, {})
    await loadSchedules()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    window.alert(`Cancel failed:\n${msg}`)
  } finally {
    cancellingIds.value.delete(s.id)
  }
}

function statusBadge(status: string): string {
  switch (status) {
    case 'active': return 'badge--success'
    case 'completed': return ''
    case 'paused': return 'badge--warning'
    case 'error': return 'badge--error'
    default: return ''
  }
}

function formatDate(ts: string | null): string {
  if (!ts) return '—'
  return new Date(ts).toLocaleString()
}

// Render trigger config as a readable single line
function formatTrigger(tc: ScheduleEntry['trigger_config']): string {
  if (!tc) return '—'
  const type = tc.type || 'unknown'
  const parts: string[] = [type]
  if (tc.delay !== undefined) parts.push(`delay=${tc.delay}s`)
  if (tc.interval !== undefined) parts.push(`interval=${tc.interval}s`)
  if (tc.run_at) parts.push(`run_at=${tc.run_at}`)
  if (tc.hour !== undefined && tc.minute !== undefined) {
    parts.push(`${String(tc.hour).padStart(2, '0')}:${String(tc.minute).padStart(2, '0')} daily`)
  }
  if (tc.cron) parts.push(`cron=${tc.cron}`)
  return parts.join(' · ')
}

// Pretty-print AISOP payload for display
function formatAisop(aisop: ScheduleEntry['aisop']): string {
  if (!aisop || aisop.length === 0) return ''
  try {
    return JSON.stringify(aisop, null, 2)
  } catch {
    return String(aisop)
  }
}

function formatTask(task: ScheduleEntry['task']): string {
  if (!task || Object.keys(task).length === 0) return ''
  try {
    return JSON.stringify(task, null, 2)
  } catch {
    return String(task)
  }
}
</script>

<template>
  <div class="schedules-page">
    <div class="page-header">
      <h2>Schedules</h2>
      <span class="badge">{{ schedules.length }}</span>
      <button class="btn-refresh" @click="loadSchedules">Refresh</button>
    </div>

    <div v-if="loading" class="loading">Loading schedules...</div>
    <div v-else-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

    <div v-else-if="schedules.length === 0" class="empty">No scheduled tasks</div>

    <div v-else class="schedule-table-wrap">
      <table class="schedule-table">
        <thead>
          <tr>
            <th class="col-expand"></th>
            <th>ID</th>
            <th>Type</th>
            <th>Status</th>
            <th>Agent</th>
            <th>Created</th>
            <th>Last Run</th>
            <th>Runs</th>
            <th class="col-actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="s in schedules" :key="s.id">
            <tr class="schedule-row" @click="toggleExpand(s.id)">
              <td class="col-expand">
                <span class="caret" :class="{ open: expandedIds.has(s.id) }">▶</span>
              </td>
              <td class="cell-id">{{ s.id }}</td>
              <td>{{ s.trigger_config?.type || '—' }}</td>
              <td><span class="badge" :class="statusBadge(s.status)">{{ s.status }}</span></td>
              <td>{{ s.from_agent }} → {{ s.to_agent }}</td>
              <td>{{ formatDate(s.created_at) }}</td>
              <td>{{ formatDate(s.last_run) }}</td>
              <td>{{ s.run_count }}</td>
              <td class="col-actions">
                <button
                  v-if="isCancellable(s)"
                  class="btn-cancel"
                  :disabled="cancellingIds.has(s.id)"
                  :title="`Cancel ${s.id}`"
                  @click="cancelSchedule(s, $event)"
                >
                  {{ cancellingIds.has(s.id) ? '...' : 'Cancel' }}
                </button>
                <span v-else class="no-action">—</span>
              </td>
            </tr>
            <tr v-if="expandedIds.has(s.id)" class="detail-row">
              <td colspan="9">
                <div class="detail-grid">
                  <div class="detail-section">
                    <div class="detail-field">
                      <span class="label">ID</span>
                      <span class="value mono">{{ s.id }}</span>
                    </div>
                    <div class="detail-field">
                      <span class="label">Status</span>
                      <span class="value">
                        <span class="badge" :class="statusBadge(s.status)">{{ s.status }}</span>
                      </span>
                    </div>
                    <div class="detail-field">
                      <span class="label">Trigger</span>
                      <span class="value mono">{{ formatTrigger(s.trigger_config) }}</span>
                    </div>
                    <div class="detail-field">
                      <span class="label">Agent</span>
                      <span class="value">{{ s.from_agent }} → {{ s.to_agent }}</span>
                    </div>
                    <div class="detail-field">
                      <span class="label">Origin</span>
                      <span class="value mono">
                        {{ s.origin_channel || '—' }}<span v-if="s.origin_user"> (user={{ s.origin_user }})</span>
                      </span>
                    </div>
                    <div class="detail-field">
                      <span class="label">Created</span>
                      <span class="value mono">{{ formatDate(s.created_at) }}</span>
                    </div>
                    <div class="detail-field">
                      <span class="label">Last Run</span>
                      <span class="value mono">{{ formatDate(s.last_run) }}</span>
                    </div>
                    <div class="detail-field">
                      <span class="label">Run Count</span>
                      <span class="value">{{ s.run_count }}</span>
                    </div>
                  </div>

                  <div v-if="formatAisop(s.aisop)" class="detail-block">
                    <details>
                      <summary class="block-summary">
                        AISOP Payload <span class="block-hint">(click to view)</span>
                      </summary>
                      <pre class="code-block">{{ formatAisop(s.aisop) }}</pre>
                    </details>
                  </div>

                  <div v-if="formatTask(s.task)" class="detail-block">
                    <details>
                      <summary class="block-summary">
                        Task Payload <span class="block-hint">(click to view)</span>
                      </summary>
                      <pre class="code-block">{{ formatTask(s.task) }}</pre>
                    </details>
                  </div>

                  <div v-if="s.last_result" class="detail-block">
                    <details>
                      <summary class="block-summary">
                        Last Result (AI reply) <span class="block-hint">({{ s.last_result.length }} chars)</span>
                      </summary>
                      <pre class="result-block">{{ s.last_result }}</pre>
                    </details>
                  </div>

                  <div v-if="s.last_error" class="detail-block">
                    <div class="error-label">Last Error</div>
                    <pre class="error-block">{{ s.last_error }}</pre>
                  </div>
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
.schedules-page {
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

.schedule-table-wrap {
  overflow-x: auto;
}

.schedule-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.schedule-table th,
.schedule-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.schedule-table th {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  background: var(--bg-card);
}

.col-expand {
  width: 24px;
  padding-right: 0 !important;
}

.caret {
  display: inline-block;
  font-size: 10px;
  color: var(--text-muted);
  transition: transform 0.15s;
  user-select: none;
}
.caret.open {
  transform: rotate(90deg);
}

.schedule-row {
  cursor: pointer;
}
.schedule-row:hover td {
  background: var(--accent-bg);
}

.cell-id {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--accent);
}

.col-actions {
  width: 80px;
  text-align: right;
}

.btn-cancel {
  background: transparent;
  color: var(--error, #e66);
  border: 1px solid var(--error, #e66);
  border-radius: var(--radius-sm);
  padding: 3px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-cancel:hover:not(:disabled) {
  background: rgba(200, 60, 60, 0.15);
}
.btn-cancel:disabled {
  opacity: 0.5;
  cursor: wait;
}

.no-action {
  color: var(--text-muted);
  font-size: 11px;
}

/* ── Expanded detail row ─────────────────────────────────── */
.detail-row > td {
  background: rgba(0, 0, 0, 0.2);
  padding: 16px 20px !important;
  border-bottom: 2px solid var(--border);
}

.detail-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-section {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 20px;
}

.detail-field {
  display: flex;
  gap: 10px;
  align-items: baseline;
  font-size: 12px;
}

.detail-field .label {
  color: var(--text-muted);
  min-width: 72px;
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.5px;
}

.detail-field .value {
  flex: 1;
  color: var(--text);
  word-break: break-word;
}

.detail-field .mono {
  font-family: var(--mono);
  font-size: 11px;
}

.detail-block {
  margin-top: 4px;
}

.block-summary {
  cursor: pointer;
  color: var(--text-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  list-style: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  user-select: none;
}
.block-summary::-webkit-details-marker { display: none; }
.block-summary::before {
  content: '\25B6';
  font-size: 9px;
  transition: transform 0.15s;
}
details[open] > .block-summary::before {
  transform: rotate(90deg);
}

.block-hint {
  color: var(--text-muted);
  text-transform: none;
  font-size: 11px;
  font-weight: normal;
  letter-spacing: normal;
}

.code-block {
  margin: 6px 0 2px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 360px;
  overflow-y: auto;
}

.result-block {
  margin: 6px 0 2px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

.error-label {
  color: var(--error, #e66);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.error-block {
  margin: 0;
  padding: 10px 12px;
  background: rgba(150, 30, 30, 0.2);
  border: 1px solid rgba(200, 60, 60, 0.4);
  border-radius: 4px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--error, #e66);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
