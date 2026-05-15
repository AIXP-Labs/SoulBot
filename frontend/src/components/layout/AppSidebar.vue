<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { path: '/chat', label: 'Chat', icon: '💬' },
  { path: '/agents', label: 'Agents', icon: '🤖' },
  { path: '/store', label: 'Store', icon: '📦' },
  { path: '/schedules', label: 'Schedules', icon: '⏰' },
  { path: '/messages', label: 'Messages', icon: '✉️' },
  { path: '/sessions', label: 'Sessions', icon: '📋' },
  { path: '/observability', label: 'Trace', icon: '📊' },
]
</script>

<template>
  <nav class="app-sidebar">
    <router-link
      v-for="item in navItems"
      :key="item.path"
      :to="item.path"
      class="nav-item"
      :class="{ active: route.path === item.path }"
    >
      <span class="nav-icon">{{ item.icon }}</span>
      <span class="nav-label">{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.app-sidebar {
  width: 60px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 8px 0;
  flex-shrink: 0;
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 4px;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 10px;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.nav-item:hover {
  color: var(--text);
  background: var(--accent-bg);
}

.nav-item.active {
  color: var(--accent);
  border-left-color: var(--accent);
  background: var(--accent-bg);
}

.nav-icon {
  font-size: 18px;
  line-height: 1;
}

.nav-label {
  font-weight: 500;
}
</style>
