<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useThemeStore } from '../../stores/theme'

const theme = useThemeStore()

const props = defineProps({
  latencyHistory: { type: Array, default: () => [] },
  heatmapData: { type: Object, default: null },
})

const canvasRef = ref(null)
const tooltipRef = ref(null)
const tooltip = ref({ show: false, x: 0, y: 0, text: '' })

// Color scale: transparent → teal → yellow → red
function getColor(count, maxCount) {
  if (count === 0) return theme.isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.03)'
  const intensity = Math.min(count / Math.max(maxCount, 1), 1)
  if (intensity < 0.33) {
    // Low: dark teal → teal
    const t = intensity / 0.33
    const r = Math.round(10 + t * 10)
    const g = Math.round(80 + t * 104)
    const b = Math.round(80 + t * 86)
    return `rgba(${r}, ${g}, ${b}, ${0.3 + t * 0.4})`
  } else if (intensity < 0.66) {
    // Mid: teal → yellow
    const t = (intensity - 0.33) / 0.33
    const r = Math.round(20 + t * 214)
    const g = Math.round(184 - t * 5)
    const b = Math.round(166 - t * 158)
    return `rgba(${r}, ${g}, ${b}, ${0.7 + t * 0.15})`
  } else {
    // High: yellow → red
    const t = (intensity - 0.66) / 0.34
    const r = Math.round(234 + t * 5)
    const g = Math.round(179 - t * 111)
    const b = Math.round(8 - t * 8)
    return `rgba(${r}, ${g}, ${b}, ${0.85 + t * 0.15})`
  }
}

function drawHeatmap() {
  const canvas = canvasRef.value
  if (!canvas || !props.heatmapData) return

  const data = props.heatmapData
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1

  // Layout constants
  const leftPad = 80
  const rightPad = 60  // for color legend
  const topPad = 10
  const bottomPad = 40

  const rect = canvas.parentElement.getBoundingClientRect()
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr
  canvas.style.width = rect.width + 'px'
  canvas.style.height = rect.height + 'px'
  ctx.scale(dpr, dpr)

  const w = rect.width
  const h = rect.height
  const gridW = w - leftPad - rightPad
  const gridH = h - topPad - bottomPad

  const numCols = data.time_labels.length
  const numRows = data.bucket_labels.length
  const cellW = gridW / numCols
  const cellH = gridH / numRows

  // Find max count for color scaling
  let maxCount = 1
  for (const row of data.grid) {
    for (const val of row) {
      if (val > maxCount) maxCount = val
    }
  }

  // Clear
  ctx.clearRect(0, 0, w, h)

  // Draw cells — x = time (columns), y = latency bucket (rows, bottom = low latency)
  for (let col = 0; col < numCols; col++) {
    for (let row = 0; row < numRows; row++) {
      const count = data.grid[col][row]
      const x = leftPad + col * cellW
      // Flip y: row 0 (lowest latency) at bottom
      const y = topPad + (numRows - 1 - row) * cellH

      ctx.fillStyle = getColor(count, maxCount)
      ctx.fillRect(x + 0.5, y + 0.5, cellW - 1, cellH - 1)

      // Cell border
      ctx.strokeStyle = theme.isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.04)'
      ctx.lineWidth = 0.5
      ctx.strokeRect(x + 0.5, y + 0.5, cellW - 1, cellH - 1)
    }
  }

  // Y-axis labels (bucket labels, bottom to top)
  ctx.fillStyle = theme.isDark ? '#555' : '#888'
  ctx.font = '10px Inter, system-ui, sans-serif'
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'
  for (let row = 0; row < numRows; row++) {
    const y = topPad + (numRows - 1 - row) * cellH + cellH / 2
    ctx.fillText(data.bucket_labels[row], leftPad - 6, y)
  }

  // X-axis labels (time, show every Nth)
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  const step = Math.max(1, Math.floor(numCols / 8))
  for (let col = 0; col < numCols; col += step) {
    const x = leftPad + col * cellW + cellW / 2
    ctx.fillText(data.time_labels[col], x, topPad + gridH + 6)
  }

  // Color legend (right side)
  const legendX = w - rightPad + 14
  const legendW = 12
  const legendH = gridH
  const legendY = topPad
  const steps = 50
  for (let i = 0; i < steps; i++) {
    const t = i / steps
    const count = Math.round(t * maxCount)
    ctx.fillStyle = getColor(count, maxCount)
    const sy = legendY + legendH - (i + 1) * (legendH / steps)
    ctx.fillRect(legendX, sy, legendW, legendH / steps + 0.5)
  }
  // Legend border
  ctx.strokeStyle = theme.isDark ? '#333' : '#ccc'
  ctx.lineWidth = 1
  ctx.strokeRect(legendX, legendY, legendW, legendH)

  // Legend labels
  ctx.fillStyle = theme.isDark ? '#555' : '#888'
  ctx.font = '9px Inter, system-ui, sans-serif'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'bottom'
  ctx.fillText('0', legendX + legendW + 4, legendY + legendH)
  ctx.textBaseline = 'top'
  ctx.fillText(String(maxCount), legendX + legendW + 4, legendY)
  ctx.textBaseline = 'middle'
  ctx.fillText(String(Math.round(maxCount / 2)), legendX + legendW + 4, legendY + legendH / 2)

  // Title label for legend
  ctx.save()
  ctx.translate(legendX + legendW + 4, legendY + legendH + 12)
  ctx.fillStyle = theme.isDark ? '#444' : '#999'
  ctx.font = '8px Inter, system-ui, sans-serif'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillText('reqs', 0, 0)
  ctx.restore()
}

function handleMouseMove(e) {
  if (!props.heatmapData || !canvasRef.value) {
    tooltip.value.show = false
    return
  }
  const data = props.heatmapData
  const rect = canvasRef.value.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top

  const leftPad = 80
  const rightPad = 60
  const topPad = 10
  const bottomPad = 40
  const gridW = rect.width - leftPad - rightPad
  const gridH = rect.height - topPad - bottomPad

  const numCols = data.time_labels.length
  const numRows = data.bucket_labels.length
  const cellW = gridW / numCols
  const cellH = gridH / numRows

  const col = Math.floor((mx - leftPad) / cellW)
  const rowFromTop = Math.floor((my - topPad) / cellH)
  const row = numRows - 1 - rowFromTop  // flip

  if (col >= 0 && col < numCols && row >= 0 && row < numRows) {
    const count = data.grid[col][row]
    tooltip.value = {
      show: true,
      x: e.clientX - rect.left + 12,
      y: e.clientY - rect.top - 10,
      text: `${data.time_labels[col]} | ${data.bucket_labels[row]} | ${count} req${count !== 1 ? 's' : ''}`,
    }
  } else {
    tooltip.value.show = false
  }
}

function handleMouseLeave() {
  tooltip.value.show = false
}

// Stats summary
const stats = computed(() => {
  if (!props.heatmapData) return null
  const d = props.heatmapData
  return { total: d.total_requests }
})

// Redraw on data or theme change
watch(() => [props.heatmapData, theme.isDark], () => { nextTick(drawHeatmap) })

let resizeObserver = null
onMounted(() => {
  nextTick(drawHeatmap)
  resizeObserver = new ResizeObserver(() => drawHeatmap())
  if (canvasRef.value?.parentElement) resizeObserver.observe(canvasRef.value.parentElement)
})
onUnmounted(() => { if (resizeObserver) resizeObserver.disconnect() })
</script>

<template>
  <div class="heatmap-container">
    <!-- Stats bar -->
    <div class="heatmap-stats" v-if="stats">
      <span class="stat-pill">
        <span class="stat-dot"></span>
        {{ stats.total }} requests (30 min)
      </span>
    </div>

    <!-- Heatmap canvas -->
    <div class="canvas-wrap" v-if="heatmapData && heatmapData.total_requests > 0">
      <canvas
        ref="canvasRef"
        @mousemove="handleMouseMove"
        @mouseleave="handleMouseLeave"
      ></canvas>
      <div
        v-if="tooltip.show"
        class="heatmap-tooltip"
        :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
      >
        {{ tooltip.text }}
      </div>
    </div>

    <!-- Empty state -->
    <div class="empty-state" v-else>
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
        <rect x="3" y="3" width="18" height="18" rx="2"/>
        <path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>
      </svg>
      <p>No latency data yet</p>
      <p class="sub">Send chat messages to populate the heatmap</p>
    </div>
  </div>
</template>

<style scoped>
.heatmap-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.heatmap-stats {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--text-tertiary);
  background: var(--hover-overlay);
  padding: 3px 10px;
  border-radius: 20px;
}

.stat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}

.canvas-wrap {
  flex: 1;
  position: relative;
  min-height: 0;
}

.canvas-wrap canvas {
  display: block;
  cursor: crosshair;
}

.heatmap-tooltip {
  position: absolute;
  pointer-events: none;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-size: 0.72rem;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 6px;
  white-space: nowrap;
  box-shadow: 0 4px 12px var(--shadow);
  z-index: 10;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-muted);
}

.empty-state p {
  font-size: 0.82rem;
  margin: 0;
}

.empty-state .sub {
  font-size: 0.72rem;
  color: var(--text-tertiary);
}
</style>
