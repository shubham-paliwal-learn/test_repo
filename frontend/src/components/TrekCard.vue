<script setup>
import { difficultyIcon, fmtDate, statusClass } from '../utils/format'

const props = defineProps({ trek: { type: Object, required: true } })
const emit = defineEmits(['view', 'book'])

const slotsFull = (t) => t.available_slots <= 0
</script>

<template>
  <div class="card trek-card h-100 shadow-sm">
    <div class="card-body d-flex flex-column">
      <div class="d-flex justify-content-between align-items-start mb-2">
        <span class="badge difficulty-badge text-capitalize" :class="trek.difficulty.toLowerCase()">
          {{ difficultyIcon(trek.difficulty) }} {{ trek.difficulty }}
        </span>
        <span class="badge" :class="statusClass(trek.status)">{{ trek.status }}</span>
      </div>
      <h5 class="card-title mb-1">{{ trek.name }}</h5>
      <p class="card-text text-muted small mb-2">📍 {{ trek.location }}<span v-if="trek.region"> · {{ trek.region }}</span></p>
      <p class="card-text small flex-grow-1 text-truncate" style="max-height: 3.2em">
        {{ trek.description || 'A beautiful Himalayan / Ghats trail organised by TMA.' }}
      </p>

      <ul class="list-unstyled small mb-2">
        <li class="d-flex justify-content-between"><span>⏱ Duration</span><strong>{{ trek.duration_days }} day(s)</strong></li>
        <li class="d-flex justify-content-between"><span>🗓 Starts</span><strong>{{ fmtDate(trek.start_date) }}</strong></li>
        <li class="d-flex justify-content-between"><span>💰 Base price</span><strong>₹{{ Number(trek.base_price || 0).toLocaleString('en-IN') }}</strong></li>
        <li class="d-flex justify-content-between">
          <span>🎟 Slots</span>
          <strong :class="{ 'text-danger': slotsFull(trek) }">{{ trek.available_slots }} / {{ trek.total_slots }}</strong>
        </li>
      </ul>

      <div class="progress slot-bar mb-3" role="progressbar" aria-label="Booked slots">
        <div
          class="progress-bar bg-success"
          :style="{ width: `${Math.round(((trek.total_slots - trek.available_slots) / Math.max(trek.total_slots, 1)) * 100)}%` }"
        ></div>
      </div>

      <div class="d-flex gap-2 mt-auto">
        <button class="btn btn-outline-primary btn-sm flex-grow-1" @click="emit('view', trek)">Details</button>
        <button
          class="btn btn-success btn-sm flex-grow-1"
          :disabled="trek.status !== 'Open' || slotsFull(trek)"
          @click="emit('book', trek)"
        >
          {{ trek.status !== 'Open' ? 'Not open' : slotsFull(trek) ? 'Sold out' : 'Book now' }}
        </button>
      </div>
    </div>
  </div>
</template>
