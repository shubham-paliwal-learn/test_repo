<script setup>
import { reactive, ref, watch } from 'vue'

const props = defineProps({ trek: { type: Object, default: null }, submitting: Boolean })
const emit = defineEmits(['confirm', 'close'])
const form = reactive({ participants: 1, notes: '' })

watch(() => props.trek, () => { form.participants = 1; form.notes = '' })

const amount = () => Number(props.trek?.base_price || 0) * form.participants
</script>

<template>
  <div v-if="trek" class="modal d-block bg-dark" style="opacity: .55" @click.self="emit('close')">
    <div class="modal-dialog modal-dialog-centered" style="opacity: 1">
      <div class="modal-content border-0 shadow rounded-4" onclick="event.stopPropagation()">
        <div class="modal-header">
          <h5 class="modal-title">Book: {{ trek.name }}</h5>
          <button type="button" class="btn-close" @click="emit('close')"></button>
        </div>
        <form novalidate @submit.prevent="emit('confirm', { participants: form.participants, notes: form.notes })">
          <div class="modal-body">
            <p class="small text-muted mb-3">
              📍 {{ trek.location }} · 🗓 Starts {{ new Date(trek.start_date).toDateString() }} ·
              Available slots: <strong>{{ trek.available_slots }}</strong>
            </p>
            <div class="mb-3">
              <label class="form-label">Participants</label>
              <input
                v-model.number="form.participants" type="number" class="form-control"
                min="1" :max="Math.max(trek.available_slots, 1)" required
              />
              <div class="form-text">Maximum {{ trek.available_slots }} participant(s) as per live slot count.</div>
            </div>
            <div class="mb-3">
              <label class="form-label">Notes <span class="text-muted">(optional)</span></label>
              <textarea v-model="form.notes" class="form-control" rows="2" maxlength="500"></textarea>
            </div>
            <div class="alert alert-success py-2 small mb-0">
              Payable amount (simulation): <strong>₹{{ amount().toLocaleString('en-IN') }}</strong>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" @click="emit('close')">Cancel</button>
            <button class="btn btn-success" :disabled="submitting || form.participants < 1 || form.participants > trek.available_slots">
              <span v-if="submitting" class="spinner-border spinner-border-sm me-2"></span>Confirm booking
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
