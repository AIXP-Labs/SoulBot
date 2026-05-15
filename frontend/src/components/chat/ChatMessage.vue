<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  type: 'user' | 'agent' | 'tool-call' | 'tool-response' | 'transfer' | 'error' | 'thinking' | 'fire-trigger'
  author: string
  text: string
  streaming?: boolean
  timestamp?: number
  summary?: string  // For fire-trigger collapsed title
}>()

marked.use({ breaks: true, gfm: true })

// L2 pattern: last ```json...``` block with "Real Done Flow" or "L0"
const l2Pattern = /```json\s*\n(\{.*?\})\s*\n?```\s*$/s

const renderedText = computed(() => {
  if (props.type === 'agent') {
    let text = props.text
    let l2Html = ''

    const m = text.match(l2Pattern)
    const rawJson = m?.[1]
    if (m && rawJson) {
      try {
        const parsed = JSON.parse(rawJson)
        if (parsed['Real Done Flow'] || parsed['L0']) {
          const idx = m.index ?? 0
          text = text.slice(0, idx).trimEnd()
          const l0 = parsed['L0'] as Record<string, unknown> | undefined
          const summary = l0
            ? Object.entries(l0).map(([k, v]) => `${k}:${v}`).join(' | ')
            : 'L2 Audit'
          const escaped = rawJson.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          l2Html = `<details class="l2-collapsible"><summary>${summary}</summary><pre><code>${escaped}</code></pre></details>`
        }
      } catch {
        // not valid JSON, keep as-is
      }
    }

    return (marked.parse(text) as string) + l2Html
  }
  return props.text
})

const isMarkdown = computed(() => props.type === 'agent')
const isTool = computed(() => props.type === 'tool-call' || props.type === 'tool-response')

const toolLabel = computed(() => {
  if (props.type === 'tool-call') return `\u{1F527} ${props.author}`
  if (props.type === 'tool-response') return `\u{2705} ${props.author}`
  return props.author
})

const timeStr = computed(() => {
  if (!props.timestamp) return ''
  const d = new Date(props.timestamp * 1000)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})
</script>

<template>
  <div class="msg" :class="[type, { streaming }]">
    <div v-if="isTool" class="msg-tool-collapsed">
      <details>
        <summary class="tool-summary">
          {{ toolLabel }}<span v-if="timeStr" class="msg-time">{{ timeStr }}</span>
        </summary>
        <pre class="tool-detail">{{ text }}</pre>
      </details>
    </div>
    <div v-else-if="type === 'fire-trigger'" class="msg-fire-collapsed">
      <details>
        <summary class="fire-summary">
          {{ summary || '⏰ Scheduled fire' }}<span v-if="timeStr" class="msg-time">{{ timeStr }}</span>
        </summary>
        <pre class="fire-detail">{{ text }}</pre>
      </details>
    </div>
    <template v-else>
      <div class="msg-author" :class="{ 'streaming-dot': streaming }">
        {{ author }}<span v-if="timeStr" class="msg-time">{{ timeStr }}</span>
      </div>
      <div v-if="type === 'thinking'" class="msg-text">
        <div class="thinking-dots"><span></span><span></span><span></span></div>
      </div>
      <div v-else-if="isMarkdown" class="msg-text markdown-body" v-html="renderedText"></div>
      <div v-else class="msg-text">{{ text }}</div>
    </template>
  </div>
</template>

<style scoped>
.msg {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  word-wrap: break-word;
}

.msg.user {
  align-self: flex-start;
  background: var(--user-bg);
  border-bottom-right-radius: 2px;
}

.msg.agent {
  align-self: flex-start;
  background: var(--agent-bg);
  border: 1px solid var(--border);
  border-bottom-left-radius: 2px;
}

.msg.tool-call,
.msg.tool-response {
  align-self: flex-start;
  background: var(--tool-bg, #1a1a2e);
  border: 1px solid #3a2a5c;
  font-family: var(--mono);
  font-size: 12px;
  max-width: 90%;
  padding: 4px 10px;
}

.msg-tool-collapsed {
  width: 100%;
}

.tool-summary {
  cursor: pointer;
  color: var(--text-muted);
  font-size: 12px;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 4px;
}
.tool-summary::-webkit-details-marker { display: none; }
.tool-summary::before {
  content: '\25B6';
  font-size: 9px;
  transition: transform 0.15s;
}
details[open] > .tool-summary::before {
  transform: rotate(90deg);
}

.tool-detail {
  margin: 6px 0 2px;
  padding: 6px 8px;
  background: rgba(0,0,0,0.25);
  border-radius: 4px;
  font-size: 11px;
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

/* Scheduled-fire trigger row — system-level audit entry */
.msg.fire-trigger {
  align-self: flex-start;
  max-width: 90%;
  background: transparent;
  border: 1px dashed var(--border);
  padding: 4px 10px;
  border-radius: 6px;
}

.msg-fire-collapsed {
  width: 100%;
}

.fire-summary {
  cursor: pointer;
  color: var(--text-muted);
  font-size: 12px;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--mono);
}
.fire-summary::-webkit-details-marker { display: none; }
.fire-summary::before {
  content: '\25B6';
  font-size: 9px;
  transition: transform 0.15s;
}
details[open] > .fire-summary::before {
  transform: rotate(90deg);
}

.fire-detail {
  margin: 6px 0 2px;
  padding: 8px 10px;
  background: rgba(0,0,0,0.25);
  border-radius: 4px;
  font-size: 11px;
  font-family: var(--mono);
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
}

.msg.transfer {
  align-self: center;
  background: var(--transfer-bg);
  border: 1px solid #2a5c3a;
  font-size: 12px;
  text-align: center;
  color: var(--accent);
  max-width: 100%;
}

.msg.error {
  align-self: flex-start;
  background: #2a1a1a;
  border: 1px solid var(--error);
  color: var(--error);
  font-size: 12px;
}

.msg.thinking {
  align-self: flex-start;
  background: var(--agent-bg);
  border: 1px solid var(--border);
  border-bottom-left-radius: 2px;
}

.msg-author {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.msg-time {
  margin-left: 8px;
  opacity: 0.6;
}

.msg-text {
  white-space: pre-wrap;
}

.msg-text.markdown-body {
  white-space: normal;
}

.msg-text.markdown-body :deep(.l2-collapsible) {
  margin-top: 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 12px;
}

.msg-text.markdown-body :deep(.l2-collapsible summary) {
  cursor: pointer;
  padding: 4px 8px;
  color: var(--text-muted);
  font-family: var(--mono);
  font-size: 11px;
  user-select: none;
}

.msg-text.markdown-body :deep(.l2-collapsible pre) {
  margin: 0;
  padding: 6px 8px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid var(--border);
  border-radius: 0 0 6px 6px;
  font-size: 11px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
