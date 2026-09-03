<template>
  <!-- Phone: the mailbox card sits above four plain numbers. -->
  <div class="flex flex-col md:hidden">
    <VirtualEmailBanner
      v-if="virtualEmail"
      class="mx-3.5 mt-3"
      :virtual-email="virtualEmail"
      :label="t('chats.mailboxLabel')"
    />
    <div class="mt-1 flex h-14 items-center px-4">
      <div
        v-for="stat in stats"
        :key="stat.key"
        class="flex flex-1 flex-col gap-px"
      >
        <span
          class="font-mono text-lg font-medium leading-[1.1]"
          :class="stat.tone"
        >
          {{ stat.value }}
        </span>
        <span class="text-[10px] text-ink-3">{{ stat.label }}</span>
      </div>
    </div>
  </div>

  <!-- Desktop: one 74px strip, numbers divided by rules, mailbox at the end. -->
  <div
    class="hidden h-[74px] flex-shrink-0 items-center border-b border-line px-5 md:flex"
  >
    <div
      v-for="(stat, index) in stats"
      :key="stat.key"
      class="flex items-baseline gap-2"
      :class="[
        index === 0 ? 'pr-7' : 'px-7',
        index < stats.length - 1 ? 'border-r border-line' : ''
      ]"
    >
      <span
        class="font-mono text-[23px] font-medium leading-none"
        :class="stat.tone"
      >
        {{ stat.value }}
      </span>
      <span class="text-[11.5px] text-ink-3">{{ stat.label }}</span>
    </div>

    <VirtualEmailBanner
      v-if="virtualEmail"
      class="ml-auto"
      :virtual-email="virtualEmail"
      :label="t('chats.mailboxLabel')"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import VirtualEmailBanner from '@/components/ui/VirtualEmailBanner.vue'

const props = defineProps({
  total: { type: Number, default: 0 },
  thisWeek: { type: Number, default: 0 },
  pending: { type: Number, default: 0 },
  completed: { type: Number, default: 0 },
  virtualEmail: { type: String, default: '' }
})

const { t } = useI18n()

const format = (value) => new Intl.NumberFormat('en-US').format(value || 0)

const stats = computed(() => [
  { key: 'total', value: format(props.total), label: t('chats.statTotal') },
  {
    key: 'week',
    value: format(props.thisWeek),
    label: t('chats.statThisWeek')
  },
  {
    key: 'pending',
    value: format(props.pending),
    label: t('chats.statPending'),
    // Waiting work is the one number worth interrupting for.
    tone: 'text-warn'
  },
  {
    key: 'completed',
    value: format(props.completed),
    label: t('chats.statCompleted')
  }
])
</script>
