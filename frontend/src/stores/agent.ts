import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, apiPost, apiDelete, apiPut } from '@/composables/useApi'
import type { AgentInfo, AisopInfo, AispInfo, TemplateInfo } from '@/types'

export const useAgentStore = defineStore('agent', () => {
  const agents = ref<string[]>([])
  const currentAgent = ref<string | null>(localStorage.getItem('soulbot:lastAgent'))
  const agentInfo = ref<Record<string, AgentInfo>>({})
  const templates = ref<TemplateInfo[]>([])
  // CLI identity from backend /cli-info — used to partition sessions by
  // provider (claude_cli / codex_cli / gemini_cli / opencode_cli / ...).
  // Updated by loadCliInfo() on startup; cached so badge UI can read it.
  const cliName = ref<string>('')

  async function loadCliInfo() {
    try {
      const info = await api<{ cli_name: string }>('/cli-info')
      cliName.value = info.cli_name || ''
    } catch {
      cliName.value = ''
    }
    return cliName.value
  }

  async function loadAgents() {
    agents.value = await api<string[]>('/list-apps')
    // Restore last agent; fallback to first if not found
    if (currentAgent.value && !agents.value.includes(currentAgent.value)) {
      currentAgent.value = null
    }
    if (!currentAgent.value && agents.value.length > 0) {
      selectAgent(agents.value[0]!)
    }
  }

  async function loadAgentInfo(name: string) {
    if (!agentInfo.value[name]) {
      agentInfo.value[name] = await api<AgentInfo>(`/apps/${name}`)
    }
    return agentInfo.value[name]
  }

  async function loadTemplates() {
    templates.value = await api<TemplateInfo[]>('/templates')
  }

  async function createAgent(name: string, template: string) {
    await apiPost('/agents/create', { name, template })
    // Refresh agent list and load info for the new agent
    await loadAgents()
    agentInfo.value[name] = await api<AgentInfo>(`/apps/${name}`)
  }

  async function deleteAgent(name: string) {
    await apiDelete(`/agents/${name}`)
    // Clear cached info
    delete agentInfo.value[name]
    // Refresh list
    await loadAgents()
  }

  async function loadAisops(agentName: string): Promise<AisopInfo[]> {
    return api<AisopInfo[]>(`/agents/${agentName}/aisops`)
  }

  async function deleteAisop(agentName: string, path: string) {
    await apiPost(`/agents/${agentName}/aisops/delete`, { path })
  }

  async function loadAisopLibrary(): Promise<AisopInfo[]> {
    return api<AisopInfo[]>('/aisop-library')
  }

  async function addAisopFromLibrary(agentName: string, group: string) {
    await apiPost(`/agents/${agentName}/aisops/add-from-library`, { group })
  }

  // --- AISP skills (doc 06; mirrors the aisops functions above) ---
  async function loadAisps(agentName: string): Promise<AispInfo[]> {
    return api<AispInfo[]>(`/agents/${agentName}/aisps`)
  }

  async function deleteAisp(agentName: string, path: string) {
    await apiPost(`/agents/${agentName}/aisps/delete`, { path })
  }

  async function loadAispLibrary(): Promise<AispInfo[]> {
    return api<AispInfo[]>('/aisp-library')
  }

  async function addAispFromLibrary(agentName: string, skill: string) {
    await apiPost(`/agents/${agentName}/aisps/add-from-library`, { skill })
  }

  async function loadAgentEnv(agentName: string): Promise<{ content: string; exists: boolean }> {
    return api<{ content: string; exists: boolean }>(`/agents/${agentName}/env`)
  }

  async function saveAgentEnv(agentName: string, content: string): Promise<{ status: string; bytes: number; note: string }> {
    return apiPut<{ name: string; status: string; bytes: number; note: string }>(
      `/agents/${agentName}/env`,
      { content },
    )
  }

  async function reloadAgent(agentName: string): Promise<{ name: string; status: string; model: string }> {
    return apiPost<{ name: string; status: string; model: string }>(
      `/agents/${agentName}/reload`,
      {},
    )
  }

  function selectAgent(name: string) {
    currentAgent.value = name
    localStorage.setItem('soulbot:lastAgent', name)
  }

  return {
    agents,
    currentAgent,
    agentInfo,
    templates,
    cliName,
    loadCliInfo,
    loadAgents,
    loadAgentInfo,
    loadTemplates,
    createAgent,
    deleteAgent,
    loadAisops,
    deleteAisop,
    loadAisopLibrary,
    reloadAgent,
    addAisopFromLibrary,
    loadAisps,
    deleteAisp,
    loadAispLibrary,
    addAispFromLibrary,
    loadAgentEnv,
    saveAgentEnv,
    selectAgent,
  }
})
