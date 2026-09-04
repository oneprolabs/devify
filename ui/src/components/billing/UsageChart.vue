<template>
  <div
    class="flex flex-col gap-3.5 rounded-[11px] border border-line bg-panel px-5 py-4"
  >
    <div class="flex flex-wrap items-baseline gap-3">
      <span class="text-[13px] font-semibold text-ink">
        {{ t('billing.usageStats.title') }}
      </span>
      <span class="font-mono text-[11px] text-ink-4">
        {{ rangeSummary }}
      </span>

      <div class="ml-auto flex gap-[5px]">
        <button
          v-for="period in periods"
          :key="period.value"
          type="button"
          class="rounded-[5px] px-[9px] py-[3px] font-mono text-[11px] transition-colors"
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

    <div class="grid grid-cols-3 gap-3">
      <div class="rounded border border-line bg-panel-sub p-3">
        <div class="text-xs text-ink-3 mb-0.5">
          {{ t('billing.usageStats.totalConsumed') }}
        </div>
        <div class="text-xl font-semibold text-ink">
          {{ stats?.total_consumed || 0 }}
        </div>
      </div>

      <div class="rounded border border-line bg-panel-sub p-3">
        <div class="text-xs text-ink-3 mb-0.5">
          {{ t('billing.usageStats.available') }}
        </div>
        <div class="text-xl font-semibold text-accent">
          {{ stats?.total_available || 0 }}
        </div>
      </div>

      <div class="rounded border border-line bg-panel-sub p-3">
        <div class="text-xs text-ink-3 mb-0.5">
          {{ t('billing.usageStats.totalCredits') }}
        </div>
        <div class="text-xl font-semibold text-ink">
          {{ stats?.total_credits || 0 }}
        </div>
      </div>
    </div>

    <div class="relative" style="height: 240px">
      <Line
        v-if="!loading && chartData"
        :data="chartData"
        :options="chartOptions"
      />
      <div v-else-if="loading" class="flex items-center justify-center h-full">
        <div class="text-ink-3">{{ t('common.loading') }}</div>
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
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import billingApi from '@/api/billing'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const { t } = useI18n()

const loading = ref(false)
const stats = ref(null)
const selectedPeriod = ref(30)
const customStartDate = ref('')
const customEndDate = ref('')

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

  const dates = stats.value.stats.map((item) => {
    const date = new Date(item.date)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  })

  const consumed = stats.value.stats.map((item) => item.consumed)

  return {
    labels: dates,
    datasets: [
      {
        label: t('billing.usageStats.creditsConsumed'),
        data: consumed,
        borderColor: accentColor(),
        backgroundColor: accentColor(0.12),
        tension: 0.3,
        fill: true
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
      ticks: {
        precision: 0
      }
    },
    x: {
      grid: {
        display: false
      }
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
