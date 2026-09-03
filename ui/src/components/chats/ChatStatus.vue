<template>
  <span class="flex items-center gap-1.5">
    <span class="h-1.5 w-1.5 flex-none rounded-full" :class="dotClass"></span>
    <span
      class="whitespace-nowrap font-mono"
      :class="[textClass, compact ? 'text-[10.5px]' : 'text-[11.5px]']"
    >
      {{ label }}
    </span>
    <!-- The bar repeats the percent the label already carries, so it sits
         beside it on a phone and under it in the table's narrow column. -->
    <span
      v-if="compact && percent !== null"
      class="h-0.5 bg-chip"
      :style="{ width: '52px' }"
    >
      <span
        class="block h-0.5 bg-warn"
        :style="{ width: `${percent}%` }"
      ></span>
    </span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  status: { type: String, required: true },
  // Only set while processing; the label appends it.
  percent: { type: Number, default: null },
  compact: { type: Boolean, default: false }
})

const { t } = useI18n()

const TONES = {
  success: { dot: 'bg-ok', text: 'text-ok' },
  processing: { dot: 'bg-warn', text: 'text-warn' },
  retrying: { dot: 'bg-warn', text: 'text-warn' },
  failed: { dot: 'bg-bad', text: 'text-bad' },
  fetched: { dot: 'bg-ink-4', text: 'text-ink-2' }
}

const tone = computed(() => TONES[props.status] || TONES.fetched)
const dotClass = computed(() => tone.value.dot)
const textClass = computed(() => tone.value.text)

// The list names states the way a reader thinks about them — a fetched row
// is one still waiting. `common.status.*` keeps the pipeline's own words,
// which the admin console overrides for its own screens.
const LABEL_KEYS = {
  success: 'chats.stateCompleted',
  processing: 'chats.stateProcessing',
  retrying: 'chats.stateProcessing',
  failed: 'chats.stateFailed',
  fetched: 'chats.statePending'
}

const label = computed(() => {
  const name = t(LABEL_KEYS[props.status] || 'common.status.unknown')
  return props.percent === null ? name : `${name} ${props.percent}%`
})
</script>
