<template>
  <div
    class="flex flex-shrink-0 flex-col gap-3 border-b border-line px-4 py-3 md:h-[74px] md:flex-row md:items-center md:gap-0 md:px-5 md:py-0"
  >
    <div class="flex items-center">
      <div
        v-for="(stat, index) in numbers"
        :key="stat.key"
        class="flex flex-1 flex-col gap-px md:flex-none md:flex-row md:items-baseline md:gap-2"
        :class="[
          index === 0 ? 'md:pr-7' : 'md:px-7',
          'md:border-r md:border-line'
        ]"
      >
        <span
          class="font-mono text-lg font-medium leading-[1.1] md:text-[23px] md:leading-none"
          :class="stat.tone"
        >
          {{ stat.value }}
        </span>
        <span class="text-[10px] text-ink-3 md:text-[11.5px]">
          {{ stat.label }}
        </span>
      </div>
    </div>

    <!-- What is left to do, split by how urgent it is. -->
    <div class="flex flex-col gap-[7px] md:w-[300px] md:pl-7">
      <div class="flex items-center justify-between">
        <span class="text-[11px] text-ink-3">
          {{ t('todos.openByPriority') }}
        </span>
        <span class="font-mono text-[10.5px] text-ink-4">{{ breakdown }}</span>
      </div>
      <div class="flex h-1.5 gap-[3px]">
        <span
          v-for="band in bands"
          :key="band.key"
          class="rounded-sm"
          :class="band.tone"
          :style="{ width: band.width }"
        ></span>
      </div>
    </div>

    <div
      class="hidden items-center gap-1.5 md:ml-auto md:flex"
      role="group"
      :aria-label="t('todos.timeRange.month')"
    >
      <button
        v-for="range in ranges"
        :key="range.value"
        type="button"
        class="font-display rounded-md px-3 py-1.5 text-xs transition-colors"
        :class="
          modelValue === range.value
            ? 'bg-accent font-medium text-accent-on'
            : 'border border-line text-ink-2'
        "
        @click="$emit('update:modelValue', range.value)"
      >
        {{ range.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  total: { type: Number, default: 0 },
  completed: { type: Number, default: 0 },
  incomplete: { type: Number, default: 0 },
  completionRate: { type: Number, default: 0 },
  // Open items split by priority, for the bar.
  byPriority: {
    type: Object,
    default: () => ({ high: 0, medium: 0, low: 0 })
  },
  // Selected time range, shown as segmented buttons on the right.
  modelValue: { type: String, default: 'month' },
  ranges: { type: Array, default: () => [] }
})

defineEmits(['update:modelValue'])

const { t } = useI18n()

const numbers = computed(() => [
  { key: 'total', value: props.total, label: t('todos.stats.total') },
  {
    key: 'completed',
    value: props.completed,
    label: t('todos.stats.completed'),
    tone: props.completed ? 'text-ok' : ''
  },
  {
    key: 'incomplete',
    value: props.incomplete,
    label: t('todos.stats.incomplete'),
    tone: props.incomplete ? 'text-warn' : ''
  },
  {
    key: 'rate',
    value: `${props.completionRate}%`,
    label: t('todos.stats.completionRate')
  }
])

const openTotal = computed(
  () =>
    (props.byPriority.high || 0) +
    (props.byPriority.medium || 0) +
    (props.byPriority.low || 0)
)

const breakdown = computed(() =>
  [
    `${t('todos.priorityShort.high')} ${props.byPriority.high || 0}`,
    `${t('todos.priorityShort.medium')} ${props.byPriority.medium || 0}`,
    `${t('todos.priorityShort.low')} ${props.byPriority.low || 0}`
  ].join(' · ')
)

// With nothing open the bar would divide by zero, so it shows an empty track.
const bands = computed(() => {
  const total = openTotal.value
  const share = (count) =>
    total ? `${((count / total) * 100).toFixed(1)}%` : '0%'

  if (!total) return [{ key: 'empty', tone: 'bg-chip', width: '100%' }]

  return [
    { key: 'high', tone: 'bg-bad', width: share(props.byPriority.high || 0) },
    {
      key: 'medium',
      tone: 'bg-warn',
      width: share(props.byPriority.medium || 0)
    },
    { key: 'low', tone: 'bg-chip', width: share(props.byPriority.low || 0) }
  ]
})
</script>
