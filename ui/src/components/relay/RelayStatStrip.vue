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
          index < numbers.length - 1 ? 'md:border-r md:border-line' : ''
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

    <div v-if="channels.length" class="flex items-center gap-2.5 md:ml-auto">
      <span class="font-mono text-[11px] text-ink-3">
        {{ t('relay.byChannel') }}
      </span>
      <div class="flex gap-[7px]">
        <span
          v-for="channel in channels"
          :key="channel.key"
          class="rounded-sm bg-chip px-2.5 py-1 font-mono text-[11px] text-ink-2"
        >
          {{ channel.label }} {{ channel.count }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  total: { type: Number, default: 0 },
  thisWeek: { type: Number, default: 0 },
  failed: { type: Number, default: 0 },
  successRate: { type: Number, default: 0 },
  // { target_type: count }
  byChannel: { type: Object, default: () => ({}) }
})

const { t } = useI18n()

const numbers = computed(() => [
  { key: 'total', value: props.total, label: t('relay.statTotal') },
  { key: 'week', value: props.thisWeek, label: t('relay.statThisWeek') },
  {
    key: 'failed',
    value: props.failed,
    label: t('relay.statFailed'),
    tone: props.failed ? 'text-bad' : ''
  },
  {
    key: 'rate',
    value: `${props.successRate}%`,
    label: t('relay.statSuccessRate')
  }
])

const CHANNEL_KEYS = {
  jira: 'relay.targetJira',
  github_issue: 'relay.targetGitHub',
  feishu_bitable: 'relay.targetFeishu'
}

const channels = computed(() =>
  Object.entries(props.byChannel).map(([key, count]) => ({
    key,
    count,
    label: t(CHANNEL_KEYS[key] || 'relay.targetFeishu')
  }))
)
</script>
