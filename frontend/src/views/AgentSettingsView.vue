<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAgentStore } from '@/stores/agent'
import type { AisopInfo, AispInfo } from '@/types'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const props = defineProps<{ name: string }>()
const router = useRouter()
const agentStore = useAgentStore()

const aisops = ref<AisopInfo[]>([])
const libraryAisops = ref<AisopInfo[]>([])
const aisps = ref<AispInfo[]>([])
const libraryAisps = ref<AispInfo[]>([])
const activeTab = ref<'aiap' | 'aisp'>('aiap')
const deleteAispTarget = ref<AispInfo | null>(null)
const loading = ref(true)
const expandedGroups = ref<Set<string>>(new Set())
const expandedLibGroups = ref<Set<string>>(new Set())
const deleteTarget = ref<AisopInfo | null>(null)
const deleteGroupTarget = ref<string | null>(null)

// .env editor state
const envContent = ref('')
const envOriginal = ref('')
const envLoading = ref(true)
const envSaving = ref(false)
const envStatus = ref('')
const envHideSecrets = ref(false)
const envDirty = computed(() => envContent.value !== envOriginal.value)

// Mask values of keys ending with TOKEN/SECRET/KEY/PASSWORD when hide is on.
const SECRET_KEY_RE = /^([A-Z][A-Z0-9_]*(?:TOKEN|SECRET|KEY|PASSWORD))=(.*)$/
const envDisplay = computed(() => {
  if (!envHideSecrets.value) return envContent.value
  return envContent.value
    .split('\n')
    .map(line => {
      const m = SECRET_KEY_RE.exec(line)
      if (m && m[2]) {
        return `${m[1]}=${'●'.repeat(Math.min(m[2].length, 12))}`
      }
      return line
    })
    .join('\n')
})

async function loadEnv() {
  envLoading.value = true
  try {
    const data = await agentStore.loadAgentEnv(props.name)
    envContent.value = data.content
    envOriginal.value = data.content
    envStatus.value = data.exists ? '' : 'No .env file (will be created on save)'
  } catch (e: unknown) {
    envStatus.value = `Load failed: ${e instanceof Error ? e.message : String(e)}`
  } finally {
    envLoading.value = false
  }
}

async function saveEnv() {
  envSaving.value = true
  envStatus.value = ''
  try {
    const result = await agentStore.saveAgentEnv(props.name, envContent.value)
    envOriginal.value = envContent.value
    envStatus.value = `Saved (${result.bytes} bytes). Reloading agent...`
    // Hot-reload this agent only (other agents unaffected, in-flight runs
    // keep the old agent instance until they complete).
    try {
      const reload = await agentStore.reloadAgent(props.name)
      envStatus.value = `Saved (${result.bytes} bytes). Reloaded — model: ${reload.model}`
    } catch (e: unknown) {
      envStatus.value = `Saved (${result.bytes} bytes), but reload failed: ${e instanceof Error ? e.message : String(e)}. Restart SoulBot manually.`
    }
  } catch (e: unknown) {
    envStatus.value = `Save failed: ${e instanceof Error ? e.message : String(e)}`
  } finally {
    envSaving.value = false
  }
}

async function reloadEnv() {
  envContent.value = envOriginal.value
  envStatus.value = 'Reverted to last saved'
}

async function loadAll() {
  // Clear stale state immediately so user doesn't see previous agent's data
  // while the new agent's data is being fetched.
  envContent.value = ''
  envOriginal.value = ''
  envStatus.value = ''
  aisops.value = []
  libraryAisops.value = []
  aisps.value = []
  libraryAisps.value = []
  loading.value = true

  try {
    const [agentAisops, libData, agentAisps, libAisps] = await Promise.all([
      agentStore.loadAisops(props.name).catch(() => [] as AisopInfo[]),
      agentStore.loadAisopLibrary().catch(() => [] as AisopInfo[]),
      agentStore.loadAisps(props.name).catch(() => [] as AispInfo[]),
      agentStore.loadAispLibrary().catch(() => [] as AispInfo[]),
    ])
    aisops.value = agentAisops
    libraryAisops.value = libData
    aisps.value = agentAisps
    libraryAisps.value = libAisps
  } catch {
    aisops.value = []
    libraryAisops.value = []
    aisps.value = []
    libraryAisps.value = []
  }
  loading.value = false
  await loadEnv()
}

onMounted(loadAll)

// Plan 18 / 01 follow-up: Vue Router reuses the component when navigating
// between /agents/:name/settings pages, so onMounted only fires once. Watch
// props.name to reload data when the user switches agent in the same view —
// otherwise the .env editor and AIAP list keep showing the previous agent.
watch(() => props.name, loadAll)

// AIAP package count (groups + ungrouped non-main files)
function aiapCount(items: AisopInfo[], mainFile: string): number {
  const groupNames = new Set<string>()
  let ungroupedCount = 0
  for (const a of items) {
    if (a.group) {
      groupNames.add(a.group)
    } else if (a.path.split('/').pop() !== mainFile) {
      ungroupedCount++
    }
  }
  return groupNames.size + ungroupedCount
}
const aisopCount = computed(() => aiapCount(aisops.value, 'main.aisop.json'))

// Current data
const currentItems = computed(() => aisops.value)
const mainFileName = computed(() => 'main.aisop.json')
const dirName = computed(() => 'aiap')
const tabLabel = computed(() => 'AIAP Applications')

// Split into ungrouped (flat) and grouped
const ungrouped = computed(() => currentItems.value.filter(a => !a.group))
const groups = computed(() => {
  const map = new Map<string, AisopInfo[]>()
  for (const a of currentItems.value) {
    if (a.group) {
      if (!map.has(a.group)) map.set(a.group, [])
      map.get(a.group)!.push(a)
    }
  }
  // Sort each group: main file first, rest alphabetical
  for (const [, items] of map) {
    items.sort((a, b) => {
      const aMain = a.path.endsWith('/' + mainFileName.value) ? 0 : 1
      const bMain = b.path.endsWith('/' + mainFileName.value) ? 0 : 1
      return aMain - bMain || a.path.localeCompare(b.path)
    })
  }
  return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]))
})

// Library: filter out groups already present in agent, then group
const libraryGroups = computed(() => {
  const agentGroupNames = new Set(currentItems.value.filter(a => a.group).map(a => a.group!))
  const agentNames = new Set(currentItems.value.map(a => a.name))
  const filtered = libraryAisops.value.filter(a => {
    if (a.group && agentGroupNames.has(a.group)) return false
    if (agentNames.has(a.name)) return false
    return true
  })
  const map = new Map<string, AisopInfo[]>()
  for (const a of filtered) {
    const key = a.group || '_flat'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(a)
  }
  for (const [, items] of map) {
    items.sort((a, b) => {
      const aMain = a.path.endsWith('/' + mainFileName.value) ? 0 : 1
      const bMain = b.path.endsWith('/' + mainFileName.value) ? 0 : 1
      return aMain - bMain || a.path.localeCompare(b.path)
    })
  }
  return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]))
})

function toggleLibGroup(group: string) {
  if (expandedLibGroups.value.has(group)) {
    expandedLibGroups.value.delete(group)
  } else {
    expandedLibGroups.value.add(group)
  }
}

function isMain(item: AisopInfo): boolean {
  return item.path.split('/').pop() === mainFileName.value
}

function toggleGroup(group: string) {
  if (expandedGroups.value.has(group)) {
    expandedGroups.value.delete(group)
  } else {
    expandedGroups.value.add(group)
  }
}

async function handleAddFromLibrary(group: string) {
  try {
    await agentStore.addAisopFromLibrary(props.name, group)
    // Refresh both lists
    const [agentData, libData] = await Promise.all([
      agentStore.loadAisops(props.name).catch(() => [] as AisopInfo[]),
      agentStore.loadAisopLibrary().catch(() => [] as AisopInfo[]),
    ])
    aisops.value = agentData
    libraryAisops.value = libData
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : String(e))
  }
}

async function handleDelete() {
  if (!deleteTarget.value) return
  const path = deleteTarget.value.path
  deleteTarget.value = null
  try {
    await agentStore.deleteAisop(props.name, path)
    aisops.value = aisops.value.filter(a => a.path !== path)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : String(e))
  }
}

async function handleDeleteGroup() {
  if (!deleteGroupTarget.value) return
  const group = deleteGroupTarget.value
  deleteGroupTarget.value = null
  try {
    await agentStore.deleteAisop(props.name, `${dirName.value}/${group}`)
    aisops.value = aisops.value.filter(a => a.group !== group)
    expandedGroups.value.delete(group)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : String(e))
  }
}

// --- AISP skills (doc 06) ---
const aispCount = computed(() => aisps.value.length)

// Library: only skills not already installed (compare by id).
const availableLibAisps = computed(() => {
  const installed = new Set(aisps.value.map(s => s.id))
  return libraryAisps.value.filter(s => !installed.has(s.id))
})

function riskClass(risk: string): string {
  return `risk-${(risk || 'unknown').toLowerCase()}`
}

async function refreshAisps() {
  const [agentData, libData] = await Promise.all([
    agentStore.loadAisps(props.name).catch(() => [] as AispInfo[]),
    agentStore.loadAispLibrary().catch(() => [] as AispInfo[]),
  ])
  aisps.value = agentData
  libraryAisps.value = libData
}

async function handleAddAisp(skill: string) {
  try {
    await agentStore.addAispFromLibrary(props.name, skill)
    await refreshAisps()
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : String(e))
  }
}

async function handleDeleteAisp() {
  if (!deleteAispTarget.value) return
  const path = deleteAispTarget.value.path
  deleteAispTarget.value = null
  try {
    await agentStore.deleteAisp(props.name, path)
    aisps.value = aisps.value.filter(s => s.path !== path)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : String(e))
  }
}

function goBack() {
  router.push({ name: 'agents' })
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <button class="btn-back" @click="goBack">&larr; Agents</button>
      <h2>{{ name }}</h2>
      <span class="header-label">Settings</span>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <template v-else>
      <div class="settings-grid">
      <div class="settings-left">
      <!-- Tabs -->
      <div class="tabs">
        <button class="tab" :class="{ active: activeTab === 'aiap' }" @click="activeTab = 'aiap'">
          AIAP Applications
          <span class="tab-count">{{ aisopCount }}</span>
        </button>
        <button class="tab" :class="{ active: activeTab === 'aisp' }" @click="activeTab = 'aisp'">
          AISP Skills
          <span class="tab-count">{{ aispCount }}</span>
        </button>
      </div>

      <!-- ===== AIAP tab ===== -->
      <template v-if="activeTab === 'aiap'">
      <!-- File List -->
      <div class="section">
        <div class="section-header">
          <h3>Agent AIAP</h3>
          <span class="badge">{{ ungrouped.filter(a => !isMain(a)).length + groups.length }}</span>
        </div>

        <div v-if="currentItems.length === 0" class="empty-state">
          No Agent AIAP files found in this agent.
        </div>

        <div v-else class="aisop-list">
          <!-- Ungrouped (flat) files first -->
          <div v-for="item in ungrouped" :key="item.path" class="aisop-card">
            <div class="aisop-header">
              <div class="aisop-header-left">
                <span class="aisop-filename">{{ item.path.split('/').pop() }}</span>
                <button
                  v-if="!isMain(item)"
                  class="btn-text-delete"
                  @click="deleteTarget = item"
                >Delete</button>
              </div>
              <span v-if="item.version" class="aisop-version">v{{ item.version }}</span>
            </div>
            <div class="aisop-name">{{ item.name }}</div>
            <div v-if="item.summary" class="aisop-summary">{{ item.summary }}</div>
            <div v-if="item.tools.length > 0" class="aisop-tools">
              <span v-for="tool in item.tools" :key="tool" class="tool-tag">{{ tool }}</span>
            </div>
          </div>

          <!-- Grouped files -->
          <div v-for="[group, items] in groups" :key="group" class="aisop-group">
            <div class="group-header">
              <button class="group-toggle" @click="toggleGroup(group)">
                <span class="toggle-icon">{{ expandedGroups.has(group) ? '&#9662;' : '&#9656;' }}</span>
                <span class="group-name">{{ group }}</span>
                <span class="group-count">({{ items.length }})</span>
              </button>
              <button
                class="btn-text-delete"
                @click="deleteGroupTarget = group"
              >Delete</button>
            </div>
            <div v-if="expandedGroups.has(group)" class="group-items">
              <div v-for="item in items" :key="item.path" class="aisop-card">
                <div class="aisop-header">
                  <span class="aisop-filename">{{ item.path.split('/').pop() }}</span>
                  <span v-if="item.version" class="aisop-version">v{{ item.version }}</span>
                </div>
                <div class="aisop-name">{{ item.name }}</div>
                <div v-if="item.summary" class="aisop-summary">{{ item.summary }}</div>
                <div v-if="item.tools.length > 0" class="aisop-tools">
                  <span v-for="tool in item.tools" :key="tool" class="tool-tag">{{ tool }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Library (only for AISOP tab) -->
      <div v-if="libraryGroups.length > 0" class="section">
        <div class="section-header">
          <h3>AIAP Store</h3>
          <span class="badge">{{ libraryGroups.filter(([g]) => g !== '_flat').length + libraryGroups.filter(([g]) => g === '_flat').reduce((n, [, items]) => n + items.filter(a => !isMain(a)).length, 0) }}</span>
        </div>

        <div class="aisop-list">
          <div v-for="[group, items] in libraryGroups" :key="'lib-' + group" class="aisop-group">
            <div v-if="group !== '_flat'" class="group-header">
              <button class="group-toggle" @click="toggleLibGroup(group)">
                <span class="toggle-icon">{{ expandedLibGroups.has(group) ? '&#9662;' : '&#9656;' }}</span>
                <span class="group-name">{{ group }}</span>
                <span class="group-count">({{ items.length }})</span>
              </button>
              <button
                class="btn-text-add"
                @click="handleAddFromLibrary(group)"
              >Add</button>
            </div>
            <!-- Flat library items -->
            <template v-if="group === '_flat'">
              <div v-for="item in items" :key="item.path" class="aisop-card lib-card">
                <div class="aisop-header">
                  <span class="aisop-filename">{{ item.path.split('/').pop() }}</span>
                  <span v-if="item.version" class="aisop-version">v{{ item.version }}</span>
                </div>
                <div class="aisop-name">{{ item.name }}</div>
                <div v-if="item.summary" class="aisop-summary">{{ item.summary }}</div>
                <div v-if="item.tools.length > 0" class="aisop-tools">
                  <span v-for="tool in item.tools" :key="tool" class="tool-tag">{{ tool }}</span>
                </div>
              </div>
            </template>
            <!-- Grouped library items -->
            <div v-else-if="expandedLibGroups.has(group)" class="group-items">
              <div v-for="item in items" :key="item.path" class="aisop-card lib-card">
                <div class="aisop-header">
                  <span class="aisop-filename">{{ item.path.split('/').pop() }}</span>
                  <span v-if="item.version" class="aisop-version">v{{ item.version }}</span>
                </div>
                <div class="aisop-name">{{ item.name }}</div>
                <div v-if="item.summary" class="aisop-summary">{{ item.summary }}</div>
                <div v-if="item.tools.length > 0" class="aisop-tools">
                  <span v-for="tool in item.tools" :key="tool" class="tool-tag">{{ tool }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      </template><!-- /AIAP tab -->

      <!-- ===== AISP tab ===== -->
      <template v-if="activeTab === 'aisp'">
      <div class="section">
        <div class="section-header">
          <h3>Agent AISP Skills</h3>
          <span class="badge">{{ aisps.length }}</span>
        </div>

        <div v-if="aisps.length === 0" class="empty-state">
          No AISP skills installed. Add one from the store below.
        </div>

        <div v-else class="aisop-list">
          <div v-for="skill in aisps" :key="skill.path" class="aisop-card">
            <div class="aisop-header">
              <div class="aisop-header-left">
                <span class="aisop-filename">{{ skill.id }}</span>
                <span class="risk-badge" :class="riskClass(skill.risk_level)">{{ skill.risk_level || 'unknown' }}</span>
                <button class="btn-text-delete" @click="deleteAispTarget = skill">Uninstall</button>
              </div>
              <span v-if="skill.version" class="aisop-version">v{{ skill.version }}</span>
            </div>
            <div class="aisop-name">{{ skill.name }}</div>
            <div v-if="skill.summary" class="aisop-summary">{{ skill.summary }}</div>
            <ul v-if="skill.when_to_use.length" class="aisp-wtu">
              <li v-for="(w, i) in skill.when_to_use" :key="i">{{ w }}</li>
            </ul>
          </div>
        </div>
        <div class="aisp-hint">Registry self-heals on the agent's next turn — no reload needed.</div>
      </div>

      <!-- AISP store -->
      <div v-if="availableLibAisps.length > 0" class="section">
        <div class="section-header">
          <h3>AISP Store</h3>
          <span class="badge">{{ availableLibAisps.length }}</span>
        </div>
        <div class="aisop-list">
          <div v-for="skill in availableLibAisps" :key="'lib-' + skill.id" class="aisop-card lib-card">
            <div class="aisop-header">
              <div class="aisop-header-left">
                <span class="aisop-filename">{{ skill.id }}</span>
                <span class="risk-badge" :class="riskClass(skill.risk_level)">{{ skill.risk_level || 'unknown' }}</span>
                <button class="btn-text-add" @click="handleAddAisp(skill.id)">Install</button>
              </div>
              <span v-if="skill.version" class="aisop-version">v{{ skill.version }}</span>
            </div>
            <div class="aisop-name">{{ skill.name }}</div>
            <div v-if="skill.summary" class="aisop-summary">{{ skill.summary }}</div>
          </div>
        </div>
      </div>
      </template><!-- /AISP tab -->
      </div><!-- /settings-left -->

      <!-- Right column: .env editor -->
      <div class="settings-right">
        <div class="section">
          <div class="section-header">
            <h3>Environment (.env)</h3>
            <label class="hide-secrets-toggle">
              <input type="checkbox" v-model="envHideSecrets" />
              Hide secrets
            </label>
          </div>
          <div v-if="envLoading" class="empty-state">Loading .env...</div>
          <template v-else>
            <textarea
              class="env-editor"
              :value="envDisplay"
              @input="envContent = ($event.target as HTMLTextAreaElement).value"
              :disabled="envHideSecrets"
              spellcheck="false"
              placeholder="# KEY=value&#10;# Each line is one variable&#10;# Lines starting with # are comments"
            ></textarea>
            <div class="env-status" v-if="envStatus">{{ envStatus }}</div>
            <div class="env-actions">
              <button
                class="btn btn-secondary"
                @click="reloadEnv"
                :disabled="envSaving || !envDirty"
              >
                Revert
              </button>
              <button
                class="btn btn-primary"
                @click="saveEnv"
                :disabled="envSaving || !envDirty || envHideSecrets"
              >
                {{ envSaving ? 'Saving...' : (envDirty ? 'Save' : 'Saved') }}
              </button>
            </div>
            <div v-if="envHideSecrets" class="env-note">
              Editing disabled while secrets are hidden. Uncheck to edit.
            </div>
          </template>
        </div>
      </div><!-- /settings-right -->
      </div><!-- /settings-grid -->
    </template>

    <ConfirmDialog
      v-if="deleteTarget"
      title="Delete File"
      :message="`Delete '${deleteTarget.path.split('/').pop()}'? This cannot be undone.`"
      confirmText="Delete"
      confirmVariant="danger"
      @confirm="handleDelete"
      @cancel="deleteTarget = null"
    />

    <ConfirmDialog
      v-if="deleteGroupTarget"
      title="Delete Group"
      :message="`Delete entire folder '${deleteGroupTarget}' and all files inside? This cannot be undone.`"
      confirmText="Delete Folder"
      confirmVariant="danger"
      @confirm="handleDeleteGroup"
      @cancel="deleteGroupTarget = null"
    />

    <ConfirmDialog
      v-if="deleteAispTarget"
      title="Uninstall AISP Skill"
      :message="`Uninstall '${deleteAispTarget.id}'? The skill folder is removed from this agent (still available in the store).`"
      confirmText="Uninstall"
      confirmVariant="danger"
      @confirm="handleDeleteAisp"
      @cancel="deleteAispTarget = null"
    />
  </div>
</template>

<style scoped>
.settings-page {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 24px;
}

.btn-back {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font);
}
.btn-back:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.page-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--accent);
}

.header-label {
  font-size: 14px;
  color: var(--text-muted);
}

.loading {
  color: var(--text-muted);
  padding: 40px;
  text-align: center;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border);
}

.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.tab:hover {
  color: var(--text);
}
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-count {
  font-size: 11px;
  font-weight: 400;
  background: var(--accent-bg);
  padding: 0 6px;
  border-radius: 8px;
  min-width: 18px;
  text-align: center;
}

.section {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.section-header h3 {
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.empty-state {
  color: var(--text-muted);
  font-size: 13px;
  padding: 24px;
  text-align: center;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.aisop-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.aisop-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
}

.aisop-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.aisop-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.aisop-filename {
  font-size: 13px;
  font-family: var(--mono);
  color: var(--accent);
  font-weight: 600;
}

.aisop-version {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--accent-bg);
  padding: 1px 8px;
  border-radius: 8px;
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

.aisop-name {
  font-size: 13px;
  color: var(--text);
  margin-bottom: 2px;
}

.aisop-summary {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
  line-height: 1.4;
}

.aisop-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tool-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: var(--tool-bg);
  color: var(--text-muted);
  border-radius: 6px;
}

/* AISP skill cards (doc 06) */
.risk-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 8px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.risk-low { background: #16351f; color: #6ee7a0; }
.risk-medium { background: #3a3016; color: #f5c451; }
.risk-high { background: #3d1a1a; color: #f38b8b; }
.risk-unknown { background: var(--tool-bg); color: var(--text-muted); }

.aisp-wtu {
  margin: 6px 0 0;
  padding-left: 16px;
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
}

.aisp-hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
  font-style: italic;
}

.aisop-group {
  margin-top: 4px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 4px;
}

.group-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--text);
  cursor: pointer;
  padding: 8px 4px;
  font-size: 14px;
  font-family: var(--font);
  text-align: left;
}
.group-toggle:hover {
  color: var(--accent);
}

.toggle-icon {
  font-size: 12px;
  width: 14px;
  text-align: center;
}

.group-name {
  font-weight: 600;
  font-family: var(--mono);
  font-size: 13px;
}

.group-count {
  color: var(--text-muted);
  font-size: 12px;
}

.group-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-left: 20px;
  padding-top: 6px;
}

.btn-text-add {
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
.btn-text-add:hover {
  opacity: 1;
  color: var(--accent);
  background: var(--accent-bg);
}

.lib-card {
  opacity: 0.75;
}
.lib-card:hover {
  opacity: 1;
}

/* Two-column grid (left = AIAP sections, right = .env editor) */
.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 460px);
  gap: 24px;
  align-items: start;
}
@media (max-width: 1100px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}

.settings-left,
.settings-right {
  min-width: 0;
}

.hide-secrets-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
}
.hide-secrets-toggle input {
  cursor: pointer;
}

.env-editor {
  width: 100%;
  min-height: 360px;
  max-height: 600px;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  white-space: pre;
  overflow-wrap: normal;
}
.env-editor:focus {
  border-color: var(--accent);
}
.env-editor:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.env-status {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 8px;
  padding: 6px 10px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

.env-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.env-note {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  font-style: italic;
}
</style>
