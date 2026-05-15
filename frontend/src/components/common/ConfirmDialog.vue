<script setup lang="ts">
defineProps<{
  title: string
  message: string
  confirmText?: string
  confirmVariant?: 'danger' | 'primary'
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <div class="modal-overlay" @click.self="emit('cancel')">
    <div class="modal-card">
      <h3 class="modal-title">{{ title }}</h3>
      <p class="modal-message">{{ message }}</p>
      <div class="modal-actions">
        <button class="btn btn-secondary" @click="emit('cancel')">Cancel</button>
        <button
          class="btn"
          :class="confirmVariant === 'danger' ? 'btn-danger' : 'btn-primary'"
          @click="emit('confirm')"
        >
          {{ confirmText || 'Confirm' }}
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
  width: 400px;
  max-width: 90vw;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.modal-message {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 20px;
  line-height: 1.5;
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

.btn-secondary {
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
}
.btn-secondary:hover {
  background: var(--border);
}

.btn-primary {
  background: var(--accent);
  color: var(--bg);
}
.btn-primary:hover {
  background: var(--accent-hover);
}

.btn-danger {
  background: var(--error);
  color: #fff;
}
.btn-danger:hover {
  background: #d32f2f;
}
</style>
