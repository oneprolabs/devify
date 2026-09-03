<template>
  <div class="bg-panel rounded-lg shadow-sm border border-line p-4">
    <div class="mb-4">
      <h3 class="text-base font-semibold text-ink mb-3">
        {{ t('billing.usageStats.title') }}
      </h3>

      <div
        class="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between"
      >
        <div class="flex gap-2">
          <button
            v-for="period in periods"
            :key="period.value"
            @click="selectPeriod(period.value)"
            :class="[
              'px-4 py-2 text-sm font-medium rounded-md transition-colors',
              selectedPeriod === period.value
                ? 'bg-accent text-accent-on'
                : 'bg-chip text-ink-2 hover:bg-chip'
            ]"
          >
            {{ period.label }}
          </button>
        </div>

        <div class="flex items-center gap-2">
          <input
            v-model="customStartDate"
            type="date"
            class="px-3 py-2 text-sm border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-accent"
            @change="handleCustomDateChange"
          />
          <span class="text-ink-3">-</span>
          <input
            v-model="customEndDate"
            type="date"
            class="px-3 py-2 text-sm border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-accent"
            @change="handleCustomDateChange"
          />
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
      <div class="bg-app-sub rounded-lg p-3">
        <div class="text-xs text-ink-3 mb-0.5">
          {{ t('billing.usageStats.totalConsumed') }}
        </div>
        <div class="text-xl font-semibold text-ink">
          {{ stats?.total_consumed || 0 }}
        </div>
      </div>

      <div class="bg-app-sub rounded-lg p-3">
        <div class="text-xs text-ink-3 mb-0.5">
          {{ t('billing.usageStats.available') }}
        </div>
        <div class="text-xl font-semibold text-accent">
          {{ stats?.total_available || 0 }}
        </div>
      </div>

      <div class="bg-app-sub rounded-lg p-3">
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
import { ref, computed, onMounted, watch } from 'vue'
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

const periods = [
  { value: 1, label: '1d' },
  { value: 7, label: '7d' },
  { value: 30, label: '30d' }
]

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

function handleCustomDateChange() {
  if (customStartDate.value && customEndDate.value) {
    selectedPeriod.value = null

    const startDate = new Date(customStartDate.value)
    const endDate = new Date(customEndDate.value)

    fetchUsageStats(startDate.toISOString(), endDate.toISOString())
  }
}

onMounted(() => {
  selectPeriod(30)
})
</script>
