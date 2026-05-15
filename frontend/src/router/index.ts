import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/chat',
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
    },
    {
      path: '/agents',
      name: 'agents',
      component: () => import('@/views/AgentsView.vue'),
    },
    {
      path: '/agents/:name/settings',
      name: 'agent-settings',
      component: () => import('@/views/AgentSettingsView.vue'),
      props: true,
    },
    {
      path: '/store',
      name: 'store',
      component: () => import('@/views/AIAPStoreView.vue'),
    },
    {
      path: '/schedules',
      name: 'schedules',
      component: () => import('@/views/SchedulesView.vue'),
    },
    {
      path: '/messages',
      name: 'messages',
      component: () => import('@/views/MessagesView.vue'),
    },
    {
      path: '/sessions',
      name: 'sessions',
      component: () => import('@/views/SessionsView.vue'),
    },
    {
      path: '/observability',
      name: 'observability',
      component: () => import('@/views/ObservabilityView.vue'),
    },
  ],
})

export default router
