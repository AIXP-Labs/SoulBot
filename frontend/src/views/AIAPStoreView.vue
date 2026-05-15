<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { api, apiPost } from '@/composables/useApi'
import type { StoreProgram } from '@/types'

const repos = ref<string[]>([])
const selectedRepo = ref('')
const newRepoInput = ref('')
const addingRepo = ref(false)
const programs = ref<StoreProgram[]>([])
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')
const agents = ref<string[]>([])

const downloadingMap = ref<Record<string, boolean>>({})
const downloadedMap = ref<Record<string, boolean>>({})
const installingMap = ref<Record<string, boolean>>({})
const installedMap = ref<Record<string, boolean>>({})
const showDropdown = ref<string | null>(null)

const filteredPrograms = computed(() => {
  if (!searchQuery.value) return programs.value
  const q = searchQuery.value.toLowerCase()
  return programs.value.filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      p.summary.toLowerCase().includes(q) ||
      p.pattern.toLowerCase().includes(q) ||
      p.tools.some((t) => t.toLowerCase().includes(q))
  )
})

function displayName(name: string) {
  return name.replace(/_aiap$/, '').replace(/_/g, ' ')
}

function repoDisplayName(repo: string) {
  return repo.split('/').pop() || repo
}

async function loadRepos() {
  try {
    repos.value = await api<string[]>('/aiap-store/repos')
    if (repos.value.length > 0 && !selectedRepo.value) {
      selectedRepo.value = repos.value[0]!
    }
  } catch {
    repos.value = []
  }
}

function selectRepo(repo: string) {
  selectedRepo.value = repo
  searchQuery.value = ''
  loadPrograms()
}

async function addRepo() {
  const repo = newRepoInput.value.trim()
  if (!repo) return
  addingRepo.value = true
  try {
    await apiPost('/aiap-store/repos/add', { repo })
    newRepoInput.value = ''
    await loadRepos()
    selectRepo(repo)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : 'Failed to add repository')
  } finally {
    addingRepo.value = false
  }
}

async function removeRepo(repo: string) {
  if (!confirm(`Remove '${repo}' from the list?`)) return
  try {
    await apiPost('/aiap-store/repos/remove', { repo })
    await loadRepos()
    if (selectedRepo.value === repo && repos.value.length > 0) {
      selectRepo(repos.value[0]!)
    }
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : 'Failed to remove repository')
  }
}

async function loadPrograms() {
  loading.value = true
  error.value = ''
  try {
    const repo = selectedRepo.value || ''
    programs.value = await api<StoreProgram[]>(`/aiap-store/programs?repo=${encodeURIComponent(repo)}`)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load'
  } finally {
    loading.value = false
  }
}

async function loadAgents() {
  try {
    agents.value = await api<string[]>('/list-apps')
  } catch {
    // non-critical
  }
}

async function downloadProgram(program: string) {
  downloadingMap.value[program] = true
  try {
    await apiPost('/aiap-store/download', { program, repo: selectedRepo.value })
    downloadedMap.value[program] = true
    setTimeout(() => {
      downloadedMap.value[program] = false
    }, 3000)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : 'Download failed')
  } finally {
    downloadingMap.value[program] = false
  }
}

function toggleDropdown(programName: string) {
  showDropdown.value = showDropdown.value === programName ? null : programName
}

async function installProgram(program: string, agentName: string) {
  showDropdown.value = null
  installingMap.value[program] = true
  try {
    await apiPost('/aiap-store/install', { program, agent_name: agentName, repo: selectedRepo.value })
    installedMap.value[program] = true
    setTimeout(() => {
      installedMap.value[program] = false
    }, 3000)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : 'Install failed')
  } finally {
    installingMap.value[program] = false
  }
}

onMounted(async () => {
  await loadRepos()
  loadPrograms()
  loadAgents()
})
</script>

<template>
  <div class="store-layout" @click="showDropdown = null">
    <!-- Left sidebar: Repositories -->
    <aside class="repo-sidebar">
      <div class="sidebar-header">Repositories</div>
      <div class="repo-list">
        <div
          v-for="repo in repos"
          :key="repo"
          class="repo-item"
          :class="{ active: selectedRepo === repo }"
          @click="selectRepo(repo)"
        >
          <div class="repo-info">
            <span class="repo-name">{{ repoDisplayName(repo) }}</span>
            <span class="repo-full">{{ repo }}</span>
          </div>
          <button
            v-if="repo !== repos[0]"
            class="btn-remove-repo"
            title="Remove"
            @click.stop="removeRepo(repo)"
          >&times;</button>
        </div>
      </div>
      <div class="add-repo">
        <input
          v-model="newRepoInput"
          type="text"
          placeholder="owner/repo"
          class="add-repo-input"
          @keyup.enter="addRepo"
        />
        <button
          class="btn-add-repo"
          :disabled="addingRepo || !newRepoInput.trim()"
          @click="addRepo"
        >+</button>
      </div>
    </aside>

    <!-- Right content: Programs -->
    <div class="store-page">
      <div class="page-header">
        <div class="header-left">
          <h2>AIAP Store</h2>
          <span class="badge">{{ filteredPrograms.length }}</span>
        </div>
        <div class="search-box">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search programs..."
            class="search-input"
          />
        </div>
      </div>

      <p class="page-subtitle">Browse and install AIAP programs from the community</p>

      <!-- Programs list -->

      <div v-if="loading" class="loading">Loading programs from AIAP Store...</div>

      <div v-else-if="error" class="error-state">
        <p>{{ error }}</p>
        <button class="btn-retry" @click="loadPrograms">Retry</button>
      </div>

      <div v-else-if="programs.length === 0" class="empty-state">
        <p>No programs available in this repository yet.</p>
      </div>

      <div v-else-if="filteredPrograms.length === 0" class="empty-state">
        <p>No programs match "{{ searchQuery }}"</p>
      </div>

      <div v-else class="table-wrapper">
        <table class="store-table">
          <thead>
            <tr>
              <th class="col-name">Name</th>
              <th class="col-pattern">Pattern</th>
              <th class="col-version">Version</th>
              <th class="col-trust">Trust</th>
              <th class="col-quality">Quality</th>
              <th class="col-modules">Modules</th>
              <th class="col-summary">Summary</th>
              <th class="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="prog in filteredPrograms" :key="prog.name">
              <td class="col-name">
                <a
                  :href="prog.github_url"
                  target="_blank"
                  rel="noopener"
                  class="program-link"
                >{{ displayName(prog.name) }}</a>
              </td>
              <td class="col-pattern">
                <span v-if="prog.pattern" class="tag pattern-tag">{{ prog.pattern }}</span>
                <span v-else class="text-muted">-</span>
              </td>
              <td class="col-version">
                <span v-if="prog.version">{{ prog.version }}</span>
                <span v-else class="text-muted">-</span>
              </td>
              <td class="col-trust">
                <span v-if="prog.trust_level" class="tag trust-tag">{{ prog.trust_level }}</span>
                <span v-else class="text-muted">-</span>
              </td>
              <td class="col-quality">
                <span v-if="prog.quality_grade" class="tag" :class="'grade-' + prog.quality_grade">
                  {{ prog.quality_grade }}
                  <template v-if="prog.quality_score">({{ prog.quality_score.toFixed(1) }})</template>
                </span>
                <span v-else class="text-muted">-</span>
              </td>
              <td class="col-modules">
                {{ prog.module_count || '-' }}
              </td>
              <td class="col-summary">
                <span class="summary-text">{{ prog.summary || '-' }}</span>
              </td>
              <td class="col-actions" @click.stop>
                <div class="action-cell">
                  <!-- Download -->
                  <button
                    v-if="downloadingMap[prog.name]"
                    class="btn-sm btn-download" disabled
                  >Downloading...</button>
                  <button
                    v-else-if="downloadedMap[prog.name]"
                    class="btn-sm btn-downloaded" disabled
                  >Downloaded</button>
                  <button
                    v-else
                    class="btn-sm btn-download"
                    @click="downloadProgram(prog.name)"
                  >Download</button>

                  <!-- Install -->
                  <div class="install-wrapper">
                    <button
                      v-if="installingMap[prog.name]"
                      class="btn-sm btn-install" disabled
                    >Installing...</button>
                    <button
                      v-else-if="installedMap[prog.name]"
                      class="btn-sm btn-installed" disabled
                    >Installed</button>
                    <button
                      v-else
                      class="btn-sm btn-install"
                      @click="toggleDropdown(prog.name)"
                    >Install</button>

                    <div
                      v-if="showDropdown === prog.name"
                      class="agent-dropdown"
                    >
                      <div class="dropdown-title">Select Agent:</div>
                      <div
                        v-for="agent in agents"
                        :key="agent"
                        class="dropdown-item"
                        @click="installProgram(prog.name, agent)"
                      >{{ agent }}</div>
                      <div v-if="agents.length === 0" class="dropdown-empty">
                        No agents available
                      </div>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.store-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ---- Sidebar ---- */
.repo-sidebar {
  width: 220px;
  min-width: 220px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
}

.sidebar-header {
  padding: 16px 14px 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.repo-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px;
}

.repo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.1s;
  margin-bottom: 2px;
}
.repo-item:hover {
  background: var(--accent-bg);
}
.repo-item.active {
  background: var(--accent-bg);
  border-left: 2px solid var(--accent);
}

.repo-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.repo-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.repo-full {
  font-size: 10px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-remove-repo {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
  flex-shrink: 0;
}
.repo-item:hover .btn-remove-repo {
  opacity: 0.6;
}
.btn-remove-repo:hover {
  opacity: 1 !important;
  color: var(--error);
}

.add-repo {
  display: flex;
  gap: 4px;
  padding: 10px;
  border-top: 1px solid var(--border);
}

.add-repo-input {
  flex: 1;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  padding: 5px 8px;
  font-size: 12px;
  font-family: var(--font);
  outline: none;
  min-width: 0;
}
.add-repo-input:focus {
  border-color: var(--accent);
}
.add-repo-input::placeholder {
  color: var(--text-muted);
}

.btn-add-repo {
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: var(--radius-sm);
  width: 28px;
  font-size: 16px;
  cursor: pointer;
  font-weight: 600;
  flex-shrink: 0;
}
.btn-add-repo:hover:not(:disabled) {
  background: var(--accent-hover);
}
.btn-add-repo:disabled {
  opacity: 0.4;
  cursor: default;
}

/* ---- Main content ---- */
.store-page {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 600;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 20px;
}

.search-input {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  padding: 6px 12px;
  font-size: 13px;
  width: 220px;
  font-family: var(--font);
  outline: none;
}
.search-input:focus {
  border-color: var(--accent);
}
.search-input::placeholder {
  color: var(--text-muted);
}

.loading {
  color: var(--text-muted);
  padding: 40px;
  text-align: center;
}

.error-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--error);
}
.error-state p {
  margin-bottom: 16px;
}

.btn-retry {
  padding: 6px 14px;
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: var(--font);
}
.btn-retry:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-muted);
  font-size: 14px;
}

/* Table */
.table-wrapper {
  overflow-x: auto;
}

.store-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.store-table th {
  text-align: left;
  padding: 10px 12px;
  color: var(--text-muted);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
}

.store-table td {
  padding: 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

.store-table tbody tr:hover {
  background: var(--accent-bg);
}

/* Column widths */
.col-name { min-width: 140px; }
.col-pattern { width: 70px; }
.col-version { width: 70px; }
.col-trust { width: 60px; }
.col-quality { width: 80px; }
.col-modules { width: 70px; text-align: center; }
.col-summary { min-width: 180px; }
.col-actions { width: 190px; white-space: nowrap; }

.store-table th.col-modules { text-align: center; }

/* Name link */
.program-link {
  color: var(--accent);
  text-decoration: none;
  font-weight: 600;
}
.program-link:hover {
  text-decoration: underline;
}

/* Tags */
.tag {
  display: inline-block;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 10px;
  font-weight: 500;
}

.pattern-tag {
  background: rgba(102, 187, 106, 0.12);
  color: var(--success);
}

.trust-tag {
  background: rgba(255, 167, 38, 0.12);
  color: var(--warning);
}

.grade-S { color: #ffd700; background: rgba(255, 215, 0, 0.12); }
.grade-A { color: var(--success); background: rgba(102, 187, 106, 0.12); }
.grade-B { color: var(--accent); background: var(--accent-bg); }
.grade-C { color: var(--warning); background: rgba(255, 167, 38, 0.12); }
.grade-D { color: var(--error); background: rgba(239, 83, 80, 0.12); }

.text-muted {
  color: var(--text-muted);
}

.summary-text {
  color: var(--text-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
  cursor: default;
  transition: all 0.2s;
}

.store-table tbody tr:hover .summary-text {
  -webkit-line-clamp: unset;
  overflow: visible;
}

/* Action buttons */
.action-cell {
  display: flex;
  gap: 6px;
  align-items: center;
}

.install-wrapper {
  position: relative;
}

.btn-sm {
  padding: 5px 12px;
  font-size: 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: var(--font);
  font-weight: 500;
  border: none;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn-download {
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
}
.btn-download:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}
.btn-download:disabled {
  cursor: wait;
  color: var(--text-muted);
}

.btn-downloaded {
  background: var(--success);
  color: var(--bg);
  cursor: default;
}

.btn-install {
  background: var(--accent);
  color: var(--bg);
}
.btn-install:hover:not(:disabled) {
  background: var(--accent-hover);
}
.btn-install:disabled {
  background: var(--bg-secondary);
  color: var(--text-muted);
  border: 1px solid var(--border);
  cursor: wait;
}

.btn-installed {
  background: var(--success);
  color: var(--bg);
  cursor: default;
}

/* Dropdown */
.agent-dropdown {
  position: absolute;
  bottom: 100%;
  right: 0;
  min-width: 160px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 10;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.dropdown-title {
  font-size: 11px;
  color: var(--text-muted);
  padding: 6px 10px 2px;
}

.dropdown-item {
  padding: 8px 10px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.1s;
}
.dropdown-item:hover {
  background: var(--accent-bg);
  color: var(--accent);
}

.dropdown-empty {
  padding: 12px 10px;
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
}
</style>
