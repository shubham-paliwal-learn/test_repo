<script setup>
import { onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import {
  Chart, BarController, BarElement, LineController, LineElement, PointElement,
  DoughnutController, ArcElement, CategoryScale, LinearScale, Tooltip, Legend, Filler,
} from 'chart.js'

Chart.register(
  BarController, BarElement, LineController, LineElement, PointElement,
  DoughnutController, ArcElement, CategoryScale, LinearScale, Tooltip, Legend, Filler,
)

const props = defineProps({
  type: { type: String, default: 'bar' }, // bar | line | doughnut
  data: { type: Object, required: true },
  height: { type: Number, default: 260 },
})

const canvas = ref(null)
let chart = null

function render() {
  if (!canvas.value) return
  if (chart) chart.destroy()
  chart = new Chart(canvas.value, {
    type: props.type,
    data: props.data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: props.type === 'doughnut' || (props.data.datasets || []).length > 1 } },
      scales: props.type === 'doughnut' ? {} : { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  })
}

onMounted(() => nextTick(render))
watch(() => [props.data, props.type], () => nextTick(render), { deep: true })
onBeforeUnmount(() => chart && chart.destroy())
</script>

<template>
  <div :style="{ height: `${height}px` }">
    <canvas ref="canvas"></canvas>
  </div>
</template>
