<template>
  <div
    class="flex cursor-pointer flex-col gap-1.5 border-b border-line-soft px-4 py-[13px] transition-colors"
    :class="selected ? 'bg-accent-soft' : 'active:bg-panel-sub'"
    @click="$emit('open', chat)"
  >
    <div class="flex items-center gap-[7px]">
      <button
        v-if="selectable"
        type="button"
        class="flex h-[15px] w-[15px] flex-none items-center justify-center rounded-sm border transition-colors"
        :class="
          selected
            ? 'border-accent bg-accent text-accent-on'
            : 'border-line text-transparent'
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

      <ChatStatus :status="status" :percent="percent" compact />

      <span
        v-if="mergedCount"
        class="rounded-sm border border-accent px-1.5 py-px font-mono text-[calc(9.5px*var(--fs))] text-accent opacity-85"
      >
        {{ t('chats.mergedBadge', { count: mergedCount }) }}
      </span>
      <span
        v-if="shared"
        class="rounded-sm border border-ok px-1.5 py-px font-mono text-[calc(9.5px*var(--fs))] text-ok opacity-85"
      >
        {{ t('share.statusShared') }}
      </span>

      <span class="ml-auto flex-none font-mono text-[calc(10.5px*var(--fs))] text-ink-4">
        {{ time }}
      </span>
    </div>

    <span class="text-sm font-semibold leading-[1.4] text-ink">
      {{ title }}
    </span>
    <span class="line-clamp-2 text-xs leading-[1.55] text-ink-3">
      {{ preview }}
    </span>

    <div
      v-if="tags.length || firstDelivery"
      class="flex items-center gap-[5px]"
    >
      <span
        v-for="tag in tags.slice(0, 2)"
        :key="tag"
        class="rounded-sm bg-chip px-1.5 py-0.5 font-mono text-[calc(10px*var(--fs))] text-ink-2"
      >
        {{ tag }}
      </span>
      <span
        v-if="firstDelivery"
        class="ml-auto truncate font-mono text-[calc(10px*var(--fs))] text-accent"
      >
        {{ relayDeliveryLabel(firstDelivery) }}
      </span>
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
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false }
})

defineEmits(['open', 'toggle'])

const { t } = useI18n()
const { getRelayDeliveries, relayDeliveryLabel } = useRelayDeliveries()

const { status, percent, title, preview, time, mergedCount, shared, tags } =
  useChatRowFields(() => props.chat)

const firstDelivery = computed(() => getRelayDeliveries(props.chat)[0] || null)
</script>
