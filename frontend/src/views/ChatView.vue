<script setup lang="ts">
import { computed, ref, watch, nextTick, onMounted, onActivated } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { useSessionStore } from '@/stores/session'
import { useSSE } from '@/composables/useSSE'
import { useSessionStream } from '@/composables/useSessionStream'
import { useTheme } from '@/composables/useTheme'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import SessionList from '@/components/chat/SessionList.vue'
import type { AgentEvent } from '@/types'

const { theme, toggle: toggleTheme } = useTheme()
const sidebarCollapsed = ref(localStorage.getItem('soulbot:sidebarCollapsed') === 'true')
watch(sidebarCollapsed, (v) => localStorage.setItem('soulbot:sidebarCollapsed', String(v)))

interface ChatMsg {
  type: 'user' | 'agent' | 'tool-call' | 'tool-response' | 'transfer' | 'error' | 'thinking' | 'fire-trigger'
  author: string
  text: string
  streaming?: boolean
  timestamp?: number
  summary?: string  // Collapsed title for fire-trigger messages
}

const agentStore = useAgentStore()
const sessionStore = useSessionStore()
const { isStreaming, error: sseError, sendMessage } = useSSE()

const messages = ref<ChatMsg[]>([])

// Long-lived SSE: only scheduled fires (reminders, heartbeat broadcasts,
// agent-to-agent pushes) — backend filters on trigger_type=="scheduled"
// so user-triggered replies don't come through here (they're delivered
// via /run_sse). Minimal safety dedup in case of accidental double-fire.
const currentSessionIdRef = computed(() => sessionStore.currentSessionId)
useSessionStream(currentSessionIdRef, (ev) => {
  const last = messages.value[messages.value.length - 1]
  if (last && last.type === 'agent' && last.text === ev.text) return
  messages.value.push({
    type: 'agent',
    author: ev.agent || 'agent',
    text: ev.text,
    timestamp: ev.timestamp,
  })
  scrollToBottom()
})
const inputText = ref('')
const chatContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const agentSelect = ref<string>('')

// Initialize
// CLI provider label for sidebar badge (claude_cli → "Claude" etc.)
const cliLabel = computed(() => {
  const raw = agentStore.cliName
  if (!raw) return ''
  const name = raw.replace(/_cli$/, '')
  return name.charAt(0).toUpperCase() + name.slice(1)
})

onMounted(async () => {
  inputRef.value?.focus()
  await agentStore.loadAgents()
  await agentStore.loadCliInfo()
  if (agentStore.currentAgent) {
    agentSelect.value = agentStore.currentAgent
    await sessionStore.loadSessions(agentStore.currentAgent)
    await loadChatHistory()
  }
})

// KeepAlive: scroll to bottom when chat tab is re-activated
// (component instance preserved, but DOM scroll position resets).
onActivated(() => {
  scrollToBottom()
})

// Watch session changes to load chat history (immediate: covers mount case)
watch(() => sessionStore.currentSessionId, async (newId) => {
  if (!newId || !agentStore.currentAgent) return
  await loadChatHistory()
}, { immediate: true })

// A scheduled-fire user message is the AISOP JSON payload
// schedule_service feeds to runner.run() when a cron task fires. The
// runner persists it as a user event. We render it as a collapsible
// "fire-trigger" system row (not as a user bubble) so the audit trail
// stays visible but doesn't pollute the conversation flow.
// Signature: starts with a JSON array containing a system role with
// AISOP protocol declaration.
function isScheduleFirePayload(text: string): boolean {
  const head = text.trimStart().slice(0, 200)
  if (!head.startsWith('[')) return false
  return /"role"\s*:\s*"system"/.test(head) && /AISOP/.test(head)
}

// Extract a short collapsed summary from a fire payload.
// Example output: "⏰ schedule.remind_drink_water · fired 22:30:31 · from heartbeat_agent"
function parseScheduleFireSummary(text: string): string {
  try {
    const parsed = JSON.parse(text.trim())
    if (!Array.isArray(parsed) || parsed.length < 1) return '⏰ Scheduled fire'
    const sys = parsed[0]?.content ?? {}
    const id = sys.id || 'scheduled'
    const describe = String(sys.describe || '')
    const fireMatch = describe.match(/fire:([^\s|]+)/)
    const fromMatch = describe.match(/from_agent:([^\s|]+)/)
    // Shorten fire timestamp to HH:MM:SS for display
    const fireTime = fireMatch?.[1] ? fireMatch[1].replace(/^\d{4}-\d{2}-\d{2}T/, '') : ''
    const parts = [`⏰ ${id}`]
    if (fireTime) parts.push(`fired ${fireTime}`)
    if (fromMatch) parts.push(`from ${fromMatch[1]}`)
    return parts.join(' · ')
  } catch {
    return '⏰ Scheduled fire'
  }
}

async function loadChatHistory() {
  if (!agentStore.currentAgent || !sessionStore.currentSessionId) return

  try {
    const detail = await sessionStore.getSessionDetail(
      agentStore.currentAgent,
      sessionStore.currentSessionId
    )

    // Auto-switch agent to match session
    if (detail.last_agent && agentStore.agents.includes(detail.last_agent)) {
      agentStore.selectAgent(detail.last_agent)
      agentSelect.value = detail.last_agent
    }

    // Build messages from events
    const msgs: ChatMsg[] = []
    for (const ev of detail.events) {
      if (ev.partial) continue
      for (const part of ev.content?.parts || []) {
        if (part.text) {
          // Scheduled-fire trigger payloads: render as collapsible
          // system row (not as user bubble) to preserve audit trail
          // without polluting conversation flow.
          if (ev.author === 'user' && isScheduleFirePayload(part.text)) {
            try {
              const pretty = JSON.stringify(JSON.parse(part.text), null, 2)
              msgs.push({
                type: 'fire-trigger',
                author: 'system',
                text: pretty,
                summary: parseScheduleFireSummary(part.text),
                timestamp: ev.timestamp,
              })
            } catch {
              // Malformed JSON — fall through to raw display below
              msgs.push({
                type: 'fire-trigger',
                author: 'system',
                text: part.text,
                summary: '⏰ Scheduled fire (unparseable payload)',
                timestamp: ev.timestamp,
              })
            }
            continue
          }
          msgs.push({
            type: ev.author === 'user' ? 'user' : 'agent',
            author: ev.author || '?',
            text: part.text,
            timestamp: ev.timestamp,
          })
        }
        if (part.function_call) {
          msgs.push({
            type: 'tool-call',
            author: part.function_call.name,
            text: JSON.stringify(part.function_call.args, null, 2),
            timestamp: ev.timestamp,
          })
        }
        if (part.function_response) {
          const raw = JSON.stringify(part.function_response.response, null, 2)
          msgs.push({
            type: 'tool-response',
            author: part.function_response.name,
            text: raw.length > 500 ? raw.slice(0, 500) + '\n...' : raw,
            timestamp: ev.timestamp,
          })
        }
      }
      if (ev.actions?.transfer_to_agent) {
        msgs.push({
          type: 'transfer',
          author: 'system',
          text: `Transferred to: ${ev.actions.transfer_to_agent}`,
          timestamp: ev.timestamp,
        })
      }
      if (ev.error_code) {
        msgs.push({
          type: 'error',
          author: ev.author || 'error',
          text: `${ev.error_code}: ${ev.error_message || ''}`,
          timestamp: ev.timestamp,
        })
      }
    }
    messages.value = msgs
    await scrollToBottom()
  } catch {
    // Session might not exist yet
    messages.value = []
  }
}

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 150) + 'px'
}

async function onSubmit() {
  const text = inputText.value.trim()
  if (!text || !agentStore.currentAgent || !sessionStore.currentSessionId) return
  if (isStreaming.value) return

  inputText.value = ''
  if (inputRef.value) inputRef.value.style.height = 'auto'
  const now = Date.now() / 1000
  messages.value.push({ type: 'user', author: 'You', text, timestamp: now })

  // Show thinking placeholder immediately so user knows the agent is working
  const agentName = agentStore.currentAgent || 'agent'
  messages.value.push({ type: 'thinking', author: agentName, text: '' })
  const thinkingIdx = messages.value.length - 1
  await scrollToBottom()

  // Streaming agent response
  let streamingIdx = -1
  let streamingText = ''
  let thinkingRemoved = false

  function removeThinking() {
    if (!thinkingRemoved && messages.value[thinkingIdx]?.type === 'thinking') {
      messages.value.splice(thinkingIdx, 1)
      thinkingRemoved = true
    }
  }

  await sendMessage(
    agentStore.currentAgent,
    'default',
    sessionStore.currentSessionId,
    text,
    (event: AgentEvent) => {
      removeThinking()
      for (const part of event.content?.parts || []) {
        if (part.function_call) {
          messages.value.push({
            type: 'tool-call',
            author: part.function_call.name,
            text: JSON.stringify(part.function_call.args, null, 2),
            timestamp: event.timestamp,
          })
          scrollToBottom()
          continue
        }
        if (part.function_response) {
          const raw = JSON.stringify(part.function_response.response, null, 2)
          messages.value.push({
            type: 'tool-response',
            author: part.function_response.name,
            text: raw.length > 500 ? raw.slice(0, 500) + '\n...' : raw,
            timestamp: event.timestamp,
          })
          scrollToBottom()
          continue
        }
        if (part.text) {
          if (event.partial) {
            streamingText += part.text
            if (streamingIdx === -1) {
              messages.value.push({
                type: 'agent',
                author: event.author || 'agent',
                text: streamingText,
                streaming: true,
                timestamp: event.timestamp,
              })
              streamingIdx = messages.value.length - 1
            } else {
              messages.value[streamingIdx]!.text = streamingText
            }
          } else {
            // Final (complete) event — use its text as the definitive version
            if (streamingIdx !== -1) {
              messages.value[streamingIdx]!.text = part.text || streamingText
              messages.value[streamingIdx]!.streaming = false
              streamingIdx = -1
              streamingText = ''
            } else {
              messages.value.push({
                type: 'agent',
                author: event.author || 'agent',
                text: part.text,
                timestamp: event.timestamp,
              })
            }
          }
          scrollToBottom()
        }
      }
      if (event.actions?.transfer_to_agent) {
        messages.value.push({
          type: 'transfer',
          author: 'system',
          text: `Transferring to: ${event.actions.transfer_to_agent}`,
          timestamp: event.timestamp,
        })
        scrollToBottom()
      }
      if (event.error_code) {
        messages.value.push({
          type: 'error',
          author: event.author || 'error',
          text: `${event.error_code}: ${event.error_message || ''}`,
          timestamp: event.timestamp,
        })
        scrollToBottom()
      }
    }
  )

  // Clean up: remove thinking placeholder if still present (e.g. empty response or error)
  removeThinking()

  // Finalize streaming
  if (streamingIdx !== -1) {
    messages.value[streamingIdx]!.streaming = false
  }

  // Refresh session list to update timestamps
  if (agentStore.currentAgent) {
    await sessionStore.loadSessions(agentStore.currentAgent)
  }

  await nextTick()
  inputRef.value?.focus()
}

async function onAgentChange() {
  agentStore.selectAgent(agentSelect.value)
  messages.value = []
  sessionStore.selectSession(null)  // reset so loadSessions auto-selects
  await sessionStore.loadSessions(agentSelect.value)
  await loadChatHistory()
}

async function scrollToBottom() {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}
</script>

<template>
  <div class="chat-layout">
    <!-- Session sidebar -->
    <div class="chat-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <template v-if="!sidebarCollapsed">
          <button class="theme-toggle" @click="toggleTheme" :title="theme === 'dark' ? 'Switch to light' : 'Switch to dark'">
            {{ theme === 'dark' ? '☀️' : '🌙' }}
          </button>
          <a href="https://www.soulbot.dev" target="_blank" class="logo-link"><span class="logo">SoulBot.dev</span></a>
          <span class="version">WebUI</span>
          <span v-if="cliLabel" class="cli-badge" :title="`Backend CLI: ${agentStore.cliName}`">{{ cliLabel }}</span>
        </template>
        <button class="sidebar-collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed" :title="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'">
          {{ sidebarCollapsed ? '»' : '«' }}
        </button>
      </div>
      <template v-if="!sidebarCollapsed">
        <div class="agent-select-row">
          <span class="label">Agent</span>
          <select v-model="agentSelect" @change="onAgentChange" class="agent-select">
            <option v-for="a in agentStore.agents" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <SessionList />
      </template>
    </div>

    <!-- Chat main area -->
    <div class="chat-main">
      <div class="chat-messages" ref="chatContainer">
        <ChatMessage
          v-for="(msg, idx) in messages"
          :key="idx"
          :type="msg.type"
          :author="msg.author"
          :text="msg.text"
          :streaming="msg.streaming"
          :timestamp="msg.timestamp"
          :summary="msg.summary"
        />
        <div v-if="messages.length === 0" class="chat-empty">
          Start a conversation...
        </div>
      </div>

      <div v-if="sseError" class="chat-error">{{ sseError }}</div>

      <form class="chat-form" @submit.prevent="onSubmit">
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="chat-input"
          placeholder="Type a message..."
          autocomplete="off"
          :disabled="isStreaming"
          rows="1"
          @keydown.enter.exact.prevent="onSubmit"
          @input="autoResize"
        />
        <button type="submit" class="btn-send" :disabled="isStreaming || !inputText.trim()">
          {{ isStreaming ? '...' : 'Send' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.chat-sidebar {
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  flex-shrink: 0;
  transition: width 0.2s ease;
}

.chat-sidebar.collapsed {
  width: auto;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  height: var(--header-height);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.sidebar-collapse-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  color: var(--text-muted);
  margin-left: auto;
}

.sidebar-collapse-btn:hover {
  background: var(--bg-card);
  color: var(--text);
}

.sidebar-header .theme-toggle {
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}

.sidebar-header .theme-toggle:hover {
  background: var(--bg-card);
}

.sidebar-header .logo-link {
  text-decoration: none;
  color: inherit;
}

.sidebar-header .logo {
  font-size: 14px;
  font-weight: 700;
  color: var(--accent);
}

.sidebar-header .version {
  font-size: 11px;
  color: var(--text-muted);
  padding: 1px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

.agent-select-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
}

.agent-select-row .label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.agent-select {
  flex: 1;
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  font-size: 12px;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--text-muted);
  font-size: 14px;
}

.chat-error {
  padding: 8px 16px;
  background: #2a1a1a;
  color: var(--error);
  font-size: 12px;
  border-top: 1px solid var(--error);
}

.chat-form {
  display: flex;
  padding: 12px;
  gap: 8px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
}

.chat-input {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  outline: none;
  font-family: var(--font);
  resize: none;
  overflow-y: auto;
  min-height: 40px;
  max-height: 150px;
  line-height: 1.4;
}
.chat-input:focus { border-color: var(--accent); }

.btn-send {
  padding: 10px 20px;
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: var(--radius);
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
  font-family: var(--font);
}
.btn-send:hover { background: var(--accent-hover); }
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
