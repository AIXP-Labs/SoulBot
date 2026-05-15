<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAgentStore } from '@/stores/agent'
import type { AgentInfo } from '@/types'
import CreateAgentModal from '@/components/agent/CreateAgentModal.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const router = useRouter()
const agentStore = useAgentStore()
const agentDetails = ref<AgentInfo[]>([])
const loading = ref(true)

const showCreateModal = ref(false)
const deleteTarget = ref<string | null>(null)

async function refreshAgents() {
  loading.value = true
  await agentStore.loadAgents()
  const details: AgentInfo[] = []
  for (const name of agentStore.agents) {
    const info = await agentStore.loadAgentInfo(name)
    details.push(info)
  }
  agentDetails.value = details
  loading.value = false
}

onMounted(refreshAgents)

async function handleCreated(_name: string) {
  showCreateModal.value = false
  // Force reload info for all agents (new one included)
  agentStore.agentInfo = {}
  await refreshAgents()
}

async function handleDelete() {
  if (!deleteTarget.value) return
  const name = deleteTarget.value
  deleteTarget.value = null
  try {
    await agentStore.deleteAgent(name)
    agentStore.agentInfo = {}
    await refreshAgents()
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : String(e))
  }
}
</script>

<template>
  <div class="agents-page">
    <div class="page-header">
      <h2>Agents</h2>
      <span class="badge">{{ agentStore.agents.length }}</span>
      <button class="btn-setting">Setting</button>
      <button class="btn-create" @click="showCreateModal = true">+ Create Agent</button>
    </div>

    <div v-if="loading" class="loading">Loading agents...</div>

    <div v-else-if="agentDetails.length === 0" class="empty-state">
      <p>No agents found.</p>
      <button class="btn-create" @click="showCreateModal = true">Create your first agent</button>
    </div>

    <div v-else class="agents-grid">
      <div v-for="agent in agentDetails" :key="agent.name" class="agent-card">
        <div class="card-header">
          <div class="agent-name">{{ agent.name }}</div>
          <div class="card-actions">
            <button
              class="btn-text-settings"
              @click="router.push({ name: 'agent-settings', params: { name: agent.name } })"
            >Settings</button>
            <button
              class="btn-text-delete"
              @click="deleteTarget = agent.name"
            >Delete</button>
          </div>
        </div>
        <div class="agent-desc">{{ agent.description || 'No description' }}</div>
        <div v-if="agent.sub_agents.length > 0" class="agent-subs">
          <span class="subs-label">Sub-agents:</span>
          <span v-for="sub in agent.sub_agents" :key="sub" class="sub-badge">{{ sub }}</span>
        </div>
      </div>
    </div>

    <CreateAgentModal
      v-if="showCreateModal"
      @close="showCreateModal = false"
      @created="handleCreated"
    />

    <ConfirmDialog
      v-if="deleteTarget"
      title="Delete Agent"
      :message="`Are you sure you want to delete '${deleteTarget}'? This will remove the agent directory and cannot be undone.`"
      confirmText="Delete"
      confirmVariant="danger"
      @confirm="handleDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<style scoped>
.agents-page {
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

.btn-setting {
  margin-left: 50px;
  padding: 6px 14px;
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  font-family: var(--font);
}
.btn-setting:hover {
  background: var(--accent-bg);
  color: var(--accent);
  border-color: var(--accent);
}

.btn-create {
  margin-left: 8px;
  padding: 6px 14px;
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  font-family: var(--font);
}
.btn-create:hover {
  background: var(--accent-hover);
}

.loading {
  color: var(--text-muted);
  padding: 40px;
  text-align: center;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-muted);
}
.empty-state p {
  margin-bottom: 16px;
  font-size: 14px;
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.agent-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.agent-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--accent);
}

.card-actions {
  display: flex;
  gap: 2px;
}

.btn-text-settings {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  opacity: 0.6;
  transition: opacity 0.15s, color 0.15s;
  font-family: var(--font);
}
.btn-text-settings:hover {
  opacity: 1;
  color: var(--accent);
  background: var(--accent-bg);
}

.btn-text-delete {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  opacity: 0.6;
  transition: opacity 0.15s, color 0.15s;
  font-family: var(--font);
}
.btn-text-delete:hover {
  opacity: 1;
  color: var(--error);
  background: rgba(239, 83, 80, 0.1);
}

.agent-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.agent-subs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.subs-label {
  font-size: 11px;
  color: var(--text-muted);
}

.sub-badge {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--accent-bg);
  color: var(--accent);
  border-radius: 10px;
}
</style>
