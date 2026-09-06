<template>
  <div
    class="flex flex-col gap-3.5 rounded-[11px] border border-line bg-panel px-5 py-4"
  >
    <div class="flex flex-wrap items-baseline gap-3">
      <span class="text-[calc(13px*var(--fs))] font-semibold text-ink">
        {{ t('billing.usageStats.title') }}
      </span>
      <span class="font-mono text-[calc(11px*var(--fs))] text-ink-4">
        {{ rangeSummary }}
      </span>

      <div class="ml-auto flex gap-[5px]">
        <button
          v-for="period in periods"
          :key="period.value"
          type="button"
          class="rounded-[5px] px-[9px] py-[3px] font-mono text-[calc(11px*var(--fs))] transition-colors"
          :class="
            selectedPeriod === period.value
              ? 'bg-accent text-accent-on'
              : 'border border-line text-ink-3 hover:border-ink-4'
          "
          @click="selectPeriod(period.value)"
        >
          {{ period.label }}
        </button>
      </div>
    </div>

    <div class="relative" style="height: 180px">
      <Bar
        v-if="!loading && chartData"
        :data="chartData"
        :options="chartOptions"
      />
      <div
        v-else-if="loading"
        class="flex h-full items-end gap-[7px] px-1 pb-5"
        aria-busy="true"
      >
        <span
          v-for="(height, index) in BAR_HEIGHTS"
          :key="index"
          class="min-w-0 flex-1 rounded-sm bg-chip"
          :style="{ height }"
        ></span>
      </div>
      <div v-else class="flex items-center justify-center h-full">
        <div class="text-ink-3">{{ t('common.noData') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'
import billingApi from '@/api/billing'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const { t } = useI18n()

const loading = ref(false)
const stats = ref(null)
const selectedPeriod = ref(30)
const customStartDate = ref('')
const customEndDate = ref('')

// A chart-shaped placeholder: fixed heights so the wait does not shimmer
// into a different silhouette on every render.
const BAR_HEIGHTS = [
  '38%', '61%', '29%', '74%', '52%', '83%', '44%', '67%',
  '31%', '58%', '77%', '41%', '69%', '35%', '55%'
]

const periods = computed(() => [
  { value: 7, label: t('billing.usageStats.days', { days: 7 }) },
  { value: 30, label: t('billing.usageStats.days', { days: 30 }) },
  { value: 90, label: t('billing.usageStats.days', { days: 90 }) }
])

// "Last 30 days · 138 credits" — the window and what it cost, together.
const rangeSummary = computed(() => {
  const total = stats.value?.total_consumed ?? 0
  return t('billing.usageStats.rangeSummary', {
    days: selectedPeriod.value,
    credits: total
  })
})

// Read the accent from the theme so the line follows light and dark
// rather than staying the blue it was hard-coded to.
function accentColor(alpha = 1) {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue('--c-ac')
    .trim()
  const channels = raw || '75 87 200'
  return alpha === 1
    ? `rgb(${channels})`
    : `rgba(${channels.split(/\s+/).join(', ')}, ${alpha})`
}

const chartData = computed(() => {
  if (!stats.value || !stats.value.stats) {
    return null
  }

  // The canvas labels the axis MM-DD, in the same mono style as the rest.
  const dates = stats.value.stats.map((item) => String(item.date).slice(5, 10))

  const consumed = stats.value.stats.map((item) => item.consumed)

  return {
    labels: dates,
    datasets: [
      {
        label: t('billing.usageStats.creditsConsumed'),
        data: consumed,
        backgroundColor: accentColor(0.45),
        hoverBackgroundColor: accentColor(),
        borderRadius: 2,
        borderSkipped: false,
        maxBarThickness: 14
      }
    ]
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      mode: 'index',
      intersect: false,
      callbacks: {
        label: function (context) {
          return `${context.dataset.label}: ${context.parsed.y} credits`
        }
      }
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      border: { display: false },
      ticks: { precision: 0, maxTicksLimit: 3, font: { size: 10 } }
    },
    x: {
      grid: { display: false },
      ticks: { maxTicksLimit: 6, font: { size: 10 } }
    }
  }
}

async function fetchUsageStats(startDate = null, endDate = null) {
  loading.value = true
  try {
    const response = await billingApi.getUsageStats(startDate, endDate)
    const statsData = response.data.data || response.data
    stats.value = statsData
  } catch (error) {
    console.error('Failed to fetch usage stats:', error)
  } finally {
    loading.value = false
  }
}

function selectPeriod(days) {
  selectedPeriod.value = days
  customStartDate.value = ''
  customEndDate.value = ''

  const endDate = new Date()
  const startDate = new Date()
  startDate.setDate(startDate.getDate() - days)

  fetchUsageStats(startDate.toISOString(), endDate.toISOString())
}

onMounted(() => {
  selectPeriod(30)
})
</script>
