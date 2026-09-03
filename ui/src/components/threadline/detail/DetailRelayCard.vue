<template>
  <PanelCard :title="t('chats.detail.deliveries')" dense flush>
    <div class="flex flex-col gap-[9px] px-4 py-2.5">
      <div
        v-for="delivery in deliveries"
        :key="relayDeliveryKey(threadline, delivery)"
        class="flex items-center gap-[9px]"
      >
        <span
          class="h-1.5 w-1.5 flex-none rounded-full"
          :class="delivery.status === 'failed' ? 'bg-bad' : 'bg-ok'"
        ></span>
        <span class="flex min-w-0 flex-col gap-px">
          <span class="truncate font-mono text-[11.5px] text-accent">
            {{ relayDeliveryLabel(delivery) }}
          </span>
          <span class="font-mono text-[10px] text-ink-4">
            {{ deliveryNote(delivery) }}
          </span>
        </span>
        <a
          v-if="delivery.external_url"
          :href="delivery.external_url"
          target="_blank"
          rel="noopener noreferrer"
          class="ml-auto flex-none text-ink-4 transition-colors hover:text-accent"
          :title="delivery.external_url"
        >
          <svg
            class="h-[13px] w-[13px]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path
              d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </a>
      </div>
    </div>
  </PanelCard>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import PanelCard from '@/components/ui/PanelCard.vue'
import { useRelayDeliveries } from '@/composables/useRelayDeliveries'

const props = defineProps({
  threadline: { type: Object, required: true },
  formatDate: { type: Function, required: true }
})

const { t } = useI18n()
const { getRelayDeliveries, relayDeliveryLabel, relayDeliveryKey } =
  useRelayDeliveries()

const deliveries = computed(() => getRelayDeliveries(props.threadline))

// The second line says what the delivery did and when, which is what
// distinguishes two rows pointing at the same channel.
const deliveryNote = (delivery) => {
  const action = delivery.action_display || delivery.action || ''
  const at = delivery.completed_at || delivery.created_at
  const stamp = at ? props.formatDate(at) : ''
  return [action, stamp].filter(Boolean).join(' · ')
}
</script>
