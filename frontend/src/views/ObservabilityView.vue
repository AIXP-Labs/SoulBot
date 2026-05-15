<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '@/composables/useApi'

interface TraceSummary {
  trace_id: string
  root_name: string
  start_time: number | string | null
  duration_ms: number
  span_count: number
  has_error: boolean
  agents: string[]
  models: string[]
}

interface SpanRecord {
  name: string
  context: { trace_id: string; span_id: string }
  parent_id: string | null
  start_time: number | string | null
  end_time: number | string | null
  status: { status_code: string; description: string }
  attributes: Record<string, unknown>
  events: Array<{ name: string; attributes?: Record<string, unknown> }>
}

interface HealthInfo {
  spans_file: string | null
  exists: boolean
  size_bytes?: number
  span_count?: number
  trace_count?: number
  reason?: string
  parse_error?: string
}

const traces = ref<TraceSummary[]>([])
const selectedTraceId = ref<string | null>(null)
const selectedSpans = ref<SpanRecord[]>([])
const health = ref<HealthInfo | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const filterSearch = ref('')
const filterStatus = ref<'' | 'OK' | 'ERROR'>('')
const filterLimit = ref<number>(20)
const autoRefresh = ref(false)
let refreshTimer: number | null = null

async function loadTraces() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams()
    params.set('limit', String(filterLimit.value))
    if (filterStatus.value) params.set('status', filterStatus.value)
    traces.value = await api<TraceSummary[]>(`/observability/traces?${params}`)
    health.value = await api<HealthInfo>('/observability/health')
    // Auto-select first trace if none selected
    const firstTrace = traces.value[0]
    if (!selectedTraceId.value && firstTrace) {
      await selectTrace(firstTrace.trace_id)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function selectTrace(traceId: string) {
  selectedTraceId.value = traceId
  selectedSpans.value = []
  try {
    selectedSpans.value = await api<SpanRecord[]>(
      `/observability/spans/${encodeURIComponent(traceId)}`
    )
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

const filteredTraces = computed(() => {
  const q = filterSearch.value.toLowerCase().trim()
  if (!q) return traces.value
  return traces.value.filter(
    (t) =>
      t.trace_id.toLowerCase().includes(q) ||
      t.root_name.toLowerCase().includes(q) ||
      t.agents.some((a) => a.toLowerCase().includes(q)) ||
      t.models.some((m) => m.toLowerCase().includes(q))
  )
})

function spanDurationMs(s: SpanRecord): number {
  const parseNs = (t: number | string | null | undefined): number | null => {
    if (t == null) return null
    if (typeof t === 'number') return t
    const ms = new Date(t).getTime()
    return isNaN(ms) ? null : ms * 1e6
  }
  const startNs = parseNs(s.start_time)
  const endNs = parseNs(s.end_time)
  if (startNs == null || endNs == null) return 0
  return (endNs - startNs) / 1e6
}

function spanAttr(s: SpanRecord, key: string): string {
  const v = s.attributes?.[key]
  return v == null ? '' : String(v)
}

function shortTraceId(tid: string): string {
  if (tid.length <= 12) return tid
  return tid.slice(0, 8) + '…' + tid.slice(-4)
}

function formatStartTime(t: number | string | null | undefined): string {
  if (t == null) return ''
  const d = typeof t === 'number' ? new Date(t / 1e6) : new Date(t)
  if (isNaN(d.getTime())) return ''
  // Local date + time (converts UTC ISO strings to user's time zone)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`
}

watch(filterStatus, () => {
  loadTraces()
})

watch(filterLimit, () => {
  loadTraces()
})

watch(autoRefresh, (on) => {
  if (refreshTimer != null) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (on) {
    refreshTimer = window.setInterval(loadTraces, 5000)
  }
})

onMounted(() => {
  loadTraces()
})

onUnmounted(() => {
  if (refreshTimer != null) {
    window.clearInterval(refreshTimer)
  }
})
</script>

<template>
  <div class="observability-view">
    <header class="obs-header">
      <div class="filters">
        <h2>📊 Trace Viewer</h2>
        <input
          v-model="filterSearch"
          placeholder="Search trace_id / span / agent / model..."
          class="filter-input"
        />
        <select v-model="filterStatus" class="filter-select">
          <option value="">All status</option>
          <option value="OK">OK only</option>
          <option value="ERROR">ERROR only</option>
        </select>
        <button @click="loadTraces" :disabled="loading" class="btn-refresh">
          {{ loading ? '...' : 'Refresh' }}
        </button>
        <label class="auto-toggle">
          <input type="checkbox" v-model="autoRefresh" />
          Auto-refresh (5s)
        </label>
        <label class="limit-input">
          Show
          <input
            type="number"
            v-model.number="filterLimit"
            min="1"
            max="1000"
            class="limit-number"
          />
          turns
        </label>
      </div>
      <div v-if="health" class="health-bar">
        <span v-if="health.exists">
          📁 {{ health.spans_file }} · {{ health.span_count }} spans · {{ health.trace_count }} traces · {{ ((health.size_bytes ?? 0) / 1024).toFixed(1) }} KB
        </span>
        <span v-else class="health-empty">
          ⚠ No spans yet — {{ health.reason ?? health.spans_file ?? 'spans file not configured' }}
        </span>
      </div>
      <div v-if="error" class="error-bar">⚠ {{ error }}</div>
    </header>

    <main class="obs-main">
      <aside class="trace-list">
        <div v-if="filteredTraces.length === 0" class="empty">
          {{ traces.length === 0 ? 'No traces. Start chatting to generate spans.' : 'No matches.' }}
        </div>
        <div
          v-for="trace in filteredTraces"
          :key="trace.trace_id"
          class="trace-item"
          :class="{
            active: selectedTraceId === trace.trace_id,
            error: trace.has_error,
          }"
          @click="selectTrace(trace.trace_id)"
        >
          <div class="trace-name">
            <span v-if="trace.has_error">❌</span>
            <span v-else>✅</span>
            {{ trace.root_name }}
          </div>
          <div class="trace-meta">
            <code>{{ shortTraceId(trace.trace_id) }}</code>
            · {{ (trace.duration_ms / 1000).toFixed(2) }}s
            · {{ trace.span_count }} sp
          </div>
          <div v-if="trace.start_time" class="trace-time">
            {{ formatStartTime(trace.start_time) }}
          </div>
          <div v-if="trace.agents.length || trace.models.length" class="trace-tags">
            <span v-for="a in trace.agents" :key="a" class="tag tag-agent">{{ a }}</span>
            <span v-for="m in trace.models" :key="m" class="tag tag-model">{{ m }}</span>
          </div>
        </div>
      </aside>

      <section class="trace-detail">
        <div v-if="!selectedTraceId" class="empty">
          ← Click a trace to view spans
        </div>
        <div v-else>
          <h3 class="detail-header">
            Trace <code>{{ selectedTraceId }}</code> · {{ selectedSpans.length }} spans
          </h3>
          <table class="span-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Duration</th>
                <th>TTFT</th>
                <th>Model</th>
                <th>Provider</th>
                <th>Status</th>
                <th>Events</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="span in selectedSpans"
                :key="span.context.span_id"
                :class="{ 'span-error': span.status?.status_code === 'ERROR' }"
              >
                <td class="span-name">{{ span.name }}</td>
                <td>{{ (spanDurationMs(span) / 1000).toFixed(3) }}s</td>
                <td>
                  {{ spanAttr(span, 'gen_ai.server.time_to_first_token') || '-' }}
                </td>
                <td>{{ spanAttr(span, 'gen_ai.request.model') || '-' }}</td>
                <td>
                  {{
                    spanAttr(span, 'gen_ai.provider.name') ||
                    spanAttr(span, 'acp.provider.name') ||
                    '-'
                  }}
                </td>
                <td>
                  <span :class="span.status?.status_code === 'ERROR' ? 'status-err' : 'status-ok'">
                    {{ span.status?.status_code || '?' }}
                  </span>
                </td>
                <td>{{ span.events?.length || 0 }}</td>
              </tr>
            </tbody>
          </table>

          <details
            v-for="span in selectedSpans.filter((s) => s.events?.length)"
            :key="`ev-${span.context.span_id}`"
            class="span-events"
          >
            <summary>
              {{ span.name }} — {{ span.events.length }} event(s)
            </summary>
            <ul>
              <li v-for="(ev, idx) in span.events" :key="idx" class="event-item">
                <strong>{{ ev.name }}</strong>
                <pre v-if="ev.attributes">{{ JSON.stringify(ev.attributes, null, 2) }}</pre>
              </li>
            </ul>
          </details>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.observability-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--bg);
  color: var(--text);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.obs-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
}

.obs-header h2 {
  margin: 0;
  font-size: 16px;
  white-space: nowrap;
  flex-shrink: 0;
}

.filters {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.filter-input {
  flex: 1 1 240px;
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg);
  color: var(--text);
  font-family: inherit;
}

.filter-select,
.btn-refresh {
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg);
  color: var(--text);
  cursor: pointer;
}

.btn-refresh:hover {
  background: var(--accent-bg);
}

.auto-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.limit-input {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.limit-number {
  width: 60px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg);
  color: var(--text);
  font-family: inherit;
}

.health-bar {
  font-size: 11px;
  color: var(--text-muted);
}

.health-empty {
  color: #b07b00;
}

.error-bar {
  font-size: 12px;
  color: #b00;
  margin-top: 4px;
}

.obs-main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.trace-list {
  width: 320px;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  background: var(--bg-secondary);
}

.trace-item {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  font-size: 12px;
  transition: background 0.1s;
}

.trace-item:hover {
  background: var(--accent-bg);
}

.trace-item.active {
  background: var(--accent-bg);
  border-left: 3px solid var(--accent);
}

.trace-item.error {
  border-left-color: #b00;
}

.trace-name {
  font-weight: 600;
  margin-bottom: 2px;
  word-break: break-word;
}

.trace-meta {
  color: var(--text-muted);
  font-size: 11px;
}

.trace-meta code {
  background: var(--bg);
  padding: 1px 4px;
  border-radius: 3px;
}

.trace-time {
  color: var(--text-muted);
  font-size: 11px;
  margin-top: 2px;
}

.trace-tags {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 9px;
  background: var(--accent-bg);
}

.tag-model {
  background: #d8e6ff;
  color: #003a8c;
}

.trace-detail {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.detail-header {
  font-size: 14px;
  margin: 0 0 12px 0;
}

.span-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin-bottom: 16px;
}

.span-table th,
.span-table td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}

.span-table th {
  background: var(--bg-secondary);
  position: sticky;
  top: 0;
}

.span-name {
  font-weight: 500;
  word-break: break-word;
}

.span-error {
  background: rgba(255, 0, 0, 0.05);
}

.status-err {
  color: #b00;
  font-weight: bold;
}

.status-ok {
  color: #0a7a0a;
}

.span-events {
  margin: 8px 0;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-secondary);
}

.span-events summary {
  cursor: pointer;
  font-size: 12px;
}

.event-item {
  margin: 6px 0;
  font-size: 11px;
}

.event-item pre {
  margin: 4px 0 0 0;
  padding: 6px 8px;
  background: var(--bg);
  border-radius: 3px;
  overflow-x: auto;
  font-size: 11px;
}

.empty {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}
</style>
