<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useAgentStore } from '@/stores/agent'

const agentStore = useAgentStore()

const emit = defineEmits<{
  close: []
  created: [name: string]
}>()

const name = ref('')
const selectedTemplate = ref('basic')
const error = ref('')
const creating = ref(false)

const namePattern = /^[a-zA-Z][a-zA-Z0-9_]{0,49}$/
const nameValid = computed(() => name.value === '' || namePattern.test(name.value))

// Auto-suffix: append "_Agent" unless user typed it already.
const finalName = computed(() => {
  if (!name.value) return ''
  return name.value.endsWith('_Agent') ? name.value : name.value + '_Agent'
})

onMounted(async () => {
  await agentStore.loadTemplates()
  if (agentStore.templates.length > 0) {
    selectedTemplate.value = agentStore.templates[0]!.name
  }
})

async function handleCreate() {
  error.value = ''
  if (!name.value) {
    error.value = 'Agent name is required'
    return
  }
  if (!namePattern.test(name.value)) {
    error.value = 'Name must start with a letter, contain only letters, digits, _, max 50 chars'
    return
  }
  creating.value = true
  try {
    await agentStore.createAgent(finalName.value, selectedTemplate.value)
    emit('created', finalName.value)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-card">
      <h3 class="modal-title">Create Agent</h3>

      <div class="form-group">
        <label class="form-label">Agent Name</label>
        <input
          v-model="name"
          class="form-input"
          :class="{ 'input-error': !nameValid }"
          placeholder="Input_Name"
          @keyup.enter="handleCreate"
        />
        <span class="field-hint">
          Suffix <code>_Agent</code> auto-appended
          <span v-if="finalName"> — will create: <code>{{ finalName }}</code></span>
        </span>
        <span v-if="!nameValid" class="field-error">
          Must start with a letter, contain only letters, digits, _
        </span>
      </div>

      <div class="form-group">
        <label class="form-label">Template</label>
        <div class="template-list">
          <label
            v-for="tpl in agentStore.templates"
            :key="tpl.name"
            class="template-option"
            :class="{ selected: selectedTemplate === tpl.name }"
          >
            <input
              type="radio"
              :value="tpl.name"
              v-model="selectedTemplate"
              class="radio-hidden"
            />
            <span class="template-name">{{ tpl.name }}</span>
            <span class="template-desc">{{ tpl.description }}</span>
          </label>
        </div>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>

      <div class="modal-actions">
        <button class="btn btn-secondary" @click="emit('close')" :disabled="creating">
          Cancel
        </button>
        <button class="btn btn-primary" @click="handleCreate" :disabled="creating || !nameValid">
          {{ creating ? 'Creating...' : 'Create' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  width: 460px;
  max-width: 90vw;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 14px;
  font-family: var(--mono);
  outline: none;
}
.form-input:focus {
  border-color: var(--accent);
}
.form-input.input-error {
  border-color: var(--error);
}

.field-error {
  display: block;
  font-size: 11px;
  color: var(--error);
  margin-top: 4px;
}

.field-hint {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}
.field-hint code {
  font-family: var(--mono);
  background: var(--bg-card);
  padding: 1px 5px;
  border-radius: 3px;
  color: var(--accent);
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color 0.15s;
}
.template-option:hover {
  border-color: var(--accent);
}
.template-option.selected {
  border-color: var(--accent);
  background: var(--accent-bg);
}

.radio-hidden {
  display: none;
}

.template-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  min-width: 60px;
}

.template-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.error-msg {
  font-size: 12px;
  color: var(--error);
  padding: 8px 12px;
  background: rgba(239, 83, 80, 0.1);
  border-radius: var(--radius-sm);
  margin-bottom: 16px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 13px;
  cursor: pointer;
  font-family: var(--font);
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
}
.btn-secondary:hover:not(:disabled) {
  background: var(--border);
}

.btn-primary {
  background: var(--accent);
  color: var(--bg);
}
.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}
</style>
