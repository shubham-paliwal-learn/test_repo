<script setup>
import { computed } from 'vue'

const props = defineProps({
  pagination: { type: Object, default: null }, // { page, per_page, total, pages }
})
const emit = defineEmits(['update'])

const pages = computed(() => {
  const p = props.pagination
  if (!p) return []
  const list = []
  const max = p.pages || 1
  const cur = p.page || 1
  for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) list.push(i)
  return list
})

function go(page) {
  if (page < 1 || page > (props.pagination?.pages || 1)) return
  emit('update', page)
}
</script>

<template>
  <nav v-if="pagination && pagination.pages > 1" class="mt-3">
    <ul class="pagination pagination-sm justify-content-center mb-0">
      <li class="page-item" :class="{ disabled: pagination.page <= 1 }">
        <a class="page-link" href="#" @click.prevent="go(pagination.page - 1)">‹</a>
      </li>
      <li v-for="p in pages" :key="p" class="page-item" :class="{ active: p === pagination.page }">
        <a class="page-link" href="#" @click.prevent="go(p)">{{ p }}</a>
      </li>
      <li class="page-item" :class="{ disabled: pagination.page >= pagination.pages }">
        <a class="page-link" href="#" @click.prevent="go(pagination.page + 1)">›</a>
      </li>
    </ul>
    <p class="text-center small text-muted mt-1 mb-0">
      {{ pagination.total }} record(s) · page {{ pagination.page }} of {{ pagination.pages }}
    </p>
  </nav>
</template>
