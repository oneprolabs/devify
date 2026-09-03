<template>
  <section
    class="flex flex-col gap-[11px] rounded-lg border border-line bg-panel px-4 py-3.5"
  >
    <div class="flex items-center justify-between">
      <span class="text-[12.5px] font-semibold text-ink">
        {{ t('chats.detail.processingStatus') }}
      </span>
      <span
        class="rounded-sm px-[7px] py-0.5 font-mono text-[10.5px]"
        :class="chipClass"
      >
        {{ statusLabel }}
      </span>
    </div>

    <div class="flex gap-1">
      <span
        v-for="(stage, index) in stages"
        :key="stage"
        class="h-[3px] flex-1 rounded-sm"
        :class="index < reached ? fillClass : 'bg-chip'"
      ></span>
    </div>

    <div class="flex justify-between font-mono text-[10px] text-ink-4">
      <span v-for="stage in stages" :key="stage">{{ t(stage) }}</span>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  status: { type: String, default: 'fetched' },
  // 0-100 while processing; ignored otherwise.
  percent: { type: Number, default: 0 }
})

const { t } = useI18n()

const stages = [
  'chats.detail.stageReceived',
  'chats.detail.stageParsed',
  'chats.detail.stageSummarised',
  'chats.detail.stageDelivered'
]

// The four bars are the pipeline, not a percentage: a fetched row has only
// arrived, a finished one has been through all four, and a failure shows how
// far it got before stopping.
const reached = computed(() => {
  if (props.status === 'success') return 4
  if (props.status === 'failed') return 1
  if (props.status === 'processing' || props.status === 'retrying') {
    return Math.min(3, 1 + Math.floor((props.percent || 0) / 40))
  }
  return 1
})

const LABELS = {
  success: 'chats.stateCompleted',
  processing: 'chats.stateProcessing',
  retrying: 'chats.stateProcessing',
  failed: 'chats.stateFailed',
  fetched: 'chats.statePending'
}

const statusLabel = computed(() =>
  t(LABELS[props.status] || 'common.status.unknown')
)

const chipClass = computed(
  () =>
    ({
      success: 'bg-ok-soft text-ok',
      processing: 'bg-warn-soft text-warn',
      retrying: 'bg-warn-soft text-warn',
      failed: 'bg-bad-soft text-bad',
      fetched: 'bg-chip text-ink-2'
    })[props.status] || 'bg-chip text-ink-2'
)

const fillClass = computed(() =>
  props.status === 'failed'
    ? 'bg-bad'
    : props.status === 'success'
      ? 'bg-ok'
      : 'bg-warn'
)
</script>
