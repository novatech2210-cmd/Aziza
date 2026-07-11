<script setup>
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler,
} from 'chart.js'
import { useThemeStore } from '../../stores/theme'

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler)

const theme = useThemeStore()

const props = defineProps({
  gpuHistory: { type: Array, default: () => [] },
})

const chartData = computed(() => ({
  labels: props.gpuHistory.map((_, i) => `${60 - props.gpuHistory.length + i}s`),
  datasets: [
    {
      label: 'GPU-0',
      data: props.gpuHistory.map((d) => d.gpu0),
      borderColor: '#14b8a6',
      backgroundColor: 'rgba(20, 184, 166, 0.08)',
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 2,
    },
  ],
}))

const chartOptions = computed(() => {
  const gridColor = theme.isDark ? '#1a1a1a' : '#e5e5e5'
  const tickColor = theme.isDark ? '#444' : '#999'
  const legendColor = theme.isDark ? '#666' : '#888'

  return {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: { min: 0, max: 100, ticks: { color: tickColor, callback: (v) => v + '%', font: { size: 10 } }, grid: { color: gridColor }, border: { color: gridColor } },
      x: { ticks: { color: tickColor, maxTicksLimit: 10, font: { size: 10 } }, grid: { display: false }, border: { color: gridColor } },
    },
    plugins: {
      legend: { labels: { color: legendColor, usePointStyle: true, pointStyle: 'line', padding: 16, font: { size: 11 } } },
    },
    animation: { duration: 0 },
  }
})
</script>

<template>
  <div style="height: 100%">
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>
