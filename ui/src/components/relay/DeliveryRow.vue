<template>
  <div
    class="flex items-center gap-[14px] border-b border-line-soft px-4 py-[var(--rowpy)] transition-colors hover:bg-panel-sub md:px-5"
  >
    <span class="flex w-20 flex-none items-center gap-1.5">
      <span class="h-1.5 w-1.5 flex-none rounded-full" :class="tone.dot"></span>
      <span
        class="whitespace-nowrap font-mono text-[calc(11.5px*var(--fs))]"
        :class="tone.text"
      >
        {{ statusLabel }}
      </span>
    </span>

    <span class="flex min-w-0 flex-1 flex-col gap-[3px]">
      <router-link
        :to="chatLink"
        class="truncate text-[calc(13.5px*var(--fs))] font-semibold text-ink transition-colors hover:text-accent"
        :title="title"
      >
        {{ title }}
      </router-link>
      <span class="truncate font-mono text-[calc(11px*var(--fs))] text-ink-4">
        {{ actionLabel }}
      </span>
    </span>

    <span
      class="hidden w-[196px] flex-none truncate font-mono text-[calc(11.5px*var(--fs))] text-ink-2 md:block"
    >
      {{ channelLabel }}
    </span>

    <span
      class="hidden w-28 flex-none truncate font-mono text-[calc(11.5px*var(--fs))] text-accent md:block"
    >
      {{ delivery.external_id || '—' }}
    </span>

    <span
      class="w-24 flex-none whitespace-nowrap text-right font-mono text-[calc(11px*var(--fs))] text-ink-4"
    >
      {{ time }}
    </span>

    <span class="flex w-[62px] flex-none justify-end">
      <button
        v-if="delivery.status === 'failed'"
        type="button"
        class="font-display rounded-md border border-bad px-2.5 py-1 text-[calc(11.5px*var(--fs))] text-bad transition-colors hover:bg-bad-soft disabled:opacity-50"
        :disabled="busy"
        @click="$emit('retry', delivery)"
      >
        {{ t('retry.retryButton') }}
      </button>
      <a
        v-else-if="delivery.external_url"
        :href="delivery.external_url"
        target="_blank"
        rel="noopener noreferrer"
        class="text-ink-4 transition-colors hover:text-accent"
        :title="delivery.external_url"
      >
        <svg
          class="h-3.5 w-3.5"
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
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRelayDeliveries } from '@/composables/useRelayDeliveries'
import { usePreferencesStore } from '@/store/preferences'
import { formatDate } from '@/utils/timezone'

const props = defineProps({
  // One delivery, carrying the event it belongs to under `event`.
  delivery: { type: Object, required: true },
  busy: { type: Boolean, default: false }
})

defineEmits(['retry'])

const { t, locale } = useI18n()
const preferences = usePreferencesStore()
const { relayDeliveryAction } = useRelayDeliveries()

const TONES = {
  success: { dot: 'bg-ok', text: 'text-ok' },
  failed: { dot: 'bg-bad', text: 'text-bad' },
  processing: { dot: 'bg-warn', text: 'text-warn' },
  pending: { dot: 'bg-ink-4', text: 'text-ink-2' },
  skipped: { dot: 'bg-ink-4', text: 'text-ink-3' }
}
const tone = computed(() => TONES[props.delivery.status] || TONES.pending)

const STATUS_KEYS = {
  success: 'common.status.success',
  failed: 'common.status.failed',
  processing: 'common.status.processing',
  pending: 'common.status.pending',
  skipped: 'relay.statusSkipped'
}
const statusLabel = computed(() =>
  t(STATUS_KEYS[props.delivery.status] || 'common.status.unknown')
)

const snapshot = computed(
  () =>
    props.delivery.event_artifact_snapshot ||
    props.delivery.event?.artifact_snapshot ||
    {}
)

const title = computed(
  () =>
    snapshot.value.summary_title ||
    snapshot.value.title ||
    snapshot.value.subject ||
    t('relay.deliveryFallbackTitle')
)

const chatLink = computed(() => {
  const event = props.delivery.event || {}
  const id = event.email_message_uuid || event.email_message || ''
  return id ? `/chats/${id}` : '/chats'
})

const actionLabel = computed(() => relayDeliveryAction(props.delivery))

const CHANNEL_KEYS = {
  jira: 'relay.targetJira',
  github_issue: 'relay.targetGitHub',
  feishu_bitable: 'relay.targetFeishu'
}
const channelLabel = computed(() => {
  const type = t(
    CHANNEL_KEYS[props.delivery.target_type] || 'relay.targetFeishu'
  )
  const name =
    props.delivery.subscription_name || props.delivery.subscription?.name
  return name ? `${type} · ${name}` : type
})

const time = computed(() => {
  const raw =
    props.delivery.completed_at ||
    props.delivery.created_at ||
    props.delivery.event?.created_at
  if (!raw) return ''

  const zone = preferences.currentTimezone
  const language = locale.value
  const clock = formatDate(raw, zone, 'HH:mm', language)
  const stamp = formatDate(raw, zone, 'yyyy-MM-dd', language)
  const today = formatDate(new Date(), zone, 'yyyy-MM-dd', language)

  return stamp === today
    ? `${t('common.today')} ${clock}`
    : `${stamp.slice(5)} ${clock}`
})
</script>
