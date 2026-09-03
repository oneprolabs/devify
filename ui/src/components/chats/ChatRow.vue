<template>
  <div
    class="flex cursor-pointer items-center gap-[14px] border-b border-line-soft px-5 py-[var(--rowpy)] transition-colors"
    :class="selected ? 'bg-panel-sub' : 'hover:bg-panel-sub'"
    @click="$emit('open', chat)"
  >
    <button
      type="button"
      class="flex h-[15px] w-[15px] flex-none items-center justify-center rounded-sm border transition-colors"
      :class="
        selected
          ? 'border-accent bg-accent text-accent-on'
          : 'border-line text-transparent hover:border-accent'
      "
      :aria-pressed="selected"
      :aria-label="t('chats.bulkMerge.selectMode')"
      @click.stop="$emit('toggle', chat)"
    >
      <svg
        class="h-2.5 w-2.5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="3.4"
        aria-hidden="true"
      >
        <path
          d="M5 12.5l4.5 4.5L19 7"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>

    <div class="flex w-[92px] flex-none flex-col gap-1">
      <ChatStatus :status="status" :percent="percent" />
      <span v-if="percent !== null" class="h-0.5 w-[66px] bg-chip">
        <span
          class="block h-0.5 bg-warn"
          :style="{ width: `${percent}%` }"
        ></span>
      </span>
    </div>

    <div class="flex min-w-0 flex-1 flex-col gap-1">
      <div class="flex items-center gap-2">
        <span
          v-if="mergedCount"
          class="rounded-sm border border-accent px-1.5 py-px font-mono text-[9.5px] text-accent opacity-85"
        >
          {{ t('chats.mergedBadge', { count: mergedCount }) }}
        </span>
        <span
          v-if="shared"
          class="rounded-sm border border-ok px-1.5 py-px font-mono text-[9.5px] text-ok opacity-85"
        >
          {{ t('share.statusShared') }}
        </span>
        <span
          v-if="chat.invoice_count > 0"
          class="rounded-sm border border-warn px-1.5 py-px font-mono text-[9.5px] text-warn opacity-85"
          :title="
            t('chats.handledByExpenseHint', { count: chat.invoice_count })
          "
        >
          {{
            t(
              'chats.handledByExpense',
              { count: chat.invoice_count },
              chat.invoice_count
            )
          }}
        </span>
        <span class="truncate text-[13.5px] font-semibold text-ink">
          {{ title }}
        </span>
      </div>
      <span class="max-w-[490px] truncate text-xs text-ink-3">
        {{ preview }}
      </span>
    </div>

    <div class="flex w-[130px] flex-none items-center gap-[5px]">
      <span
        v-for="tag in visibleTags"
        :key="tag"
        class="rounded-sm bg-chip px-1.5 py-0.5 font-mono text-[10px] text-ink-2"
      >
        {{ tag }}
      </span>
      <span v-if="hiddenTagCount" class="font-mono text-[10px] text-ink-4">
        +{{ hiddenTagCount }}
      </span>
    </div>

    <div class="w-[150px] flex-none truncate font-mono text-[11px] text-ink-2">
      {{ source }}
    </div>

    <div class="w-[108px] flex-none truncate font-mono text-[11px]">
      <button
        v-if="status === 'failed'"
        type="button"
        class="text-bad hover:underline"
        @click.stop="$emit('retry', chat)"
      >
        {{ t('retry.retryButton') }}
      </button>
      <a
        v-else-if="firstDelivery?.external_url"
        :href="firstDelivery.external_url"
        target="_blank"
        rel="noopener noreferrer"
        class="text-accent hover:underline"
        :title="firstDelivery.external_url"
        @click.stop
      >
        {{ relayDeliveryLabel(firstDelivery) }}
      </a>
      <span v-else-if="firstDelivery" class="text-ink-2">
        {{ relayDeliveryLabel(firstDelivery) }}
      </span>
      <span v-else class="text-ink-4">—</span>
    </div>

    <div
      class="w-[88px] flex-none whitespace-nowrap text-right font-mono text-[11px] text-ink-4"
    >
      {{ time }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ChatStatus from './ChatStatus.vue'
import { useRelayDeliveries } from '@/composables/useRelayDeliveries'
import { useChatRowFields } from '@/composables/useChatRowFields'

const props = defineProps({
  chat: { type: Object, required: true },
  selected: { type: Boolean, default: false }
})

defineEmits(['open', 'toggle', 'retry'])

const { t } = useI18n()
const { getRelayDeliveries, relayDeliveryLabel } = useRelayDeliveries()

const {
  status,
  percent,
  title,
  preview,
  source,
  time,
  mergedCount,
  shared,
  tags
} = useChatRowFields(() => props.chat)

const visibleTags = computed(() => tags.value.slice(0, 2))
const hiddenTagCount = computed(() => Math.max(0, tags.value.length - 2))
const firstDelivery = computed(() => getRelayDeliveries(props.chat)[0] || null)
</script>
