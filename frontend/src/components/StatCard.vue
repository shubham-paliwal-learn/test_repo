<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: 0 },
  icon: { type: String, default: '📊' },
  variant: { type: String, default: 'primary' },
  hint: { type: String, default: '' },
})
</script>

<template>
  <div class="card stat-card h-100">
    <div class="card-body d-flex align-items-center gap-3">
      <div
        class="rounded-circle bg-opacity-10 d-flex align-items-center justify-content-center flex-shrink-0"
        :class="`bg-${variant} text-${variant}`"
        style="width: 56px; height: 56px; font-size: 1.6rem"
      >
        {{ icon }}
      </div>
      <div>
        <div class="stat-value">{{ value }}</div>
        <div class="stat-label">{{ label }}</div>
        <div v-if="hint" class="small text-muted">{{ hint }}</div>
      </div>
    </div>
  </div>
</template>
