<template>
  <!-- What the list row already knows is drawn for real; only what has to
       come back from the API is a placeholder. The reader can tell which
       conversation they opened before the request finishes.

       Every card here mirrors the metrics of the real one it stands in for,
       so nothing shifts when the data lands. -->
  <div
    class="flex min-h-0 flex-1 flex-col overflow-y-auto p-4 md:flex-row"
    :class="
      variant === 'drawer' ? 'gap-[18px] md:p-5' : 'gap-5 md:gap-5 md:p-6'
    "
    aria-busy="true"
  >
    <div class="flex min-w-0 flex-1 flex-col gap-3">
      <div class="flex flex-col gap-2">
        <div class="flex flex-wrap items-center gap-[9px]">
          <span
            v-if="mergedCount"
            class="rounded-sm border border-accent px-1.5 py-0.5 font-mono text-[calc(10px*var(--fs))] text-accent opacity-85"
          >
            {{ t('chats.mergedBadge', { count: mergedCount }) }}
          </span>
          <span
            class="rounded-sm px-[7px] py-0.5 font-mono text-[calc(10px*var(--fs))]"
            :class="statusChipClass"
          >
            {{ statusLabel }}
          </span>
        </div>
        <h1
          class="text-[calc(21px*var(--fs))] font-semibold leading-[1.35] tracking-tight text-ink"
        >
          {{ title }}
        </h1>
      </div>

      <PanelCard :title="t('chats.detail.coreTopic')">
        <template #icon>
          <svg
            class="h-[15px] w-[15px] text-accent"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
            aria-hidden="true"
          >
            <path d="M4 6h16M4 12h16M4 18h9" stroke-linecap="round" />
          </svg>
        </template>
        <div class="flex flex-col gap-[9px]">
          <span
            v-for="(width, index) in SUMMARY_LINES"
            :key="index"
            class="h-[9px] rounded-[5px] bg-chip"
            :style="{ width }"
          ></span>
        </div>
      </PanelCard>

      <PanelCard :title="t('todos.newFormat.todos')" flush>
        <template #icon>
          <svg
            class="h-[15px] w-[15px] text-accent"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
            aria-hidden="true"
          >
            <rect x="3.5" y="3.5" width="17" height="17" rx="4" />
            <path
              d="M8.5 12l2.5 2.5 4.5-5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </template>
        <template #header>
          <span class="h-2 w-14 rounded bg-line-soft"></span>
        </template>

        <div
          v-for="(row, index) in TODO_ROWS"
          :key="index"
          class="flex items-start gap-[11px] px-4 py-3"
          :class="
            index < TODO_ROWS.length - 1 ? 'border-b border-line-soft' : ''
          "
          :style="{ opacity: index === TODO_ROWS.length - 1 ? 0.55 : 1 }"
        >
          <span
            class="mt-px h-4 w-4 flex-none rounded-sm border border-line"
          ></span>
          <span class="flex min-w-0 flex-1 flex-col gap-[7px]">
            <span
              class="h-[9px] rounded-[5px] bg-chip"
              :style="{ width: row[0] }"
            ></span>
            <span
              class="h-2 rounded bg-line-soft"
              :style="{ width: row[1] }"
            ></span>
          </span>
        </div>
      </PanelCard>

      <PanelCard :title="t('todos.newFormat.keyProcess')">
        <template #icon>
          <svg
            class="h-[15px] w-[15px] text-accent"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
            aria-hidden="true"
          >
            <path
              d="M12 3v18M12 3l-5 5M12 3l5 5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </template>
        <div class="flex flex-col gap-[11px]">
          <span
            v-for="(width, index) in PROCESS_LINES"
            :key="index"
            class="flex items-center gap-[11px]"
            :style="{ opacity: index === PROCESS_LINES.length - 1 ? 0.55 : 1 }"
          >
            <span
              class="h-[18px] w-[18px] flex-none rounded-full border border-line"
            ></span>
            <span
              class="h-[9px] rounded-[5px] bg-chip"
              :style="{ width }"
            ></span>
          </span>
        </div>
      </PanelCard>

      <!-- The row knows how many files arrived, so the count is real and a
           conversation with none draws no card at all. -->
      <PanelCard
        v-if="attachmentCount"
        :title="t('chats.files.title')"
        :meta="String(attachmentCount)"
      >
        <template #icon>
          <svg
            class="h-[15px] w-[15px] text-accent"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
            aria-hidden="true"
          >
            <path
              d="M21 11l-8.5 8.5a5 5 0 01-7-7L14 4a3.5 3.5 0 015 5l-8.5 8.5a2 2 0 01-3-3L15 6"
              stroke-linecap="round"
            />
          </svg>
        </template>
        <div class="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          <span
            v-for="tile in attachmentTiles"
            :key="tile.key"
            class="flex min-w-0 items-center gap-[9px] rounded border border-line px-3 py-2.5"
            :style="{ opacity: tile.opacity }"
          >
            <span class="h-7 w-7 flex-none rounded-md bg-chip"></span>
            <span class="flex min-w-0 flex-1 flex-col gap-[5px]">
              <span
                class="h-2 rounded bg-chip"
                :style="{ width: tile.name }"
              ></span>
              <span
                class="h-[7px] rounded bg-line-soft"
                :style="{ width: tile.size }"
              ></span>
            </span>
          </span>
        </div>
      </PanelCard>

      <div class="flex flex-col gap-2.5 md:flex-row">
        <span
          v-for="label in disclosureLabels"
          :key="label"
          class="flex h-[42px] min-w-0 flex-1 items-center gap-[9px] rounded-[9px] border border-line px-3.5 text-ink-3"
        >
          <svg
            class="h-3.5 w-3.5 flex-none"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            aria-hidden="true"
          >
            <path
              d="M9 6l6 6-6 6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <span class="truncate text-xs">{{ label }}</span>
        </span>
      </div>
    </div>

    <aside
      class="flex w-full flex-col gap-3 md:flex-none"
      :class="variant === 'drawer' ? 'md:w-[296px]' : 'md:w-80 md:gap-3.5'"
    >
      <DetailStatusCard :status="status" :percent="percent || 0" />

      <PanelCard :title="t('metadata.sectionTitle')" dense>
        <div class="flex flex-col gap-[9px]">
          <div class="flex min-w-0 gap-3">
            <span class="w-[52px] flex-none text-[calc(11.5px*var(--fs))] text-ink-3">
              {{ t('chats.from') }}
            </span>
            <span class="truncate text-[calc(11.5px*var(--fs))] text-ink">{{ senderName }}</span>
          </div>
          <div class="flex min-w-0 gap-3">
            <span class="w-[52px] flex-none text-[calc(11.5px*var(--fs))] text-ink-3">
              {{ t('chats.detail.receivedAt') }}
            </span>
            <span class="font-mono text-[calc(11px*var(--fs))] text-ink">
              {{ receivedAt }}
            </span>
          </div>
          <div
            v-for="field in INFO_FIELDS"
            :key="field.label"
            class="flex items-center gap-3"
          >
            <span class="w-[52px] flex-none text-[calc(11.5px*var(--fs))] text-ink-3">
              {{ t(field.label) }}
            </span>
            <span
              class="h-2 rounded bg-chip"
              :style="{ width: field.width }"
            ></span>
          </div>
        </div>
      </PanelCard>

      <PanelCard v-if="tags.length" :title="t('metadata.keywords.title')" dense>
        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="tag in tags"
            :key="tag"
            class="rounded-sm bg-chip px-2 py-[3px] font-mono text-[calc(10.5px*var(--fs))] text-ink-2"
          >
            {{ tag }}
          </span>
        </div>
      </PanelCard>

      <PanelCard
        v-if="deliveries.length"
        :title="t('chats.detail.deliveries')"
        dense
        flush
      >
        <div class="flex flex-col gap-[9px] px-4 py-2.5">
          <div
            v-for="delivery in deliveries"
            :key="relayDeliveryKey(seed, delivery)"
            class="flex items-center gap-[9px]"
          >
            <span
              class="h-1.5 w-1.5 flex-none rounded-full"
              :class="delivery.status === 'failed' ? 'bg-bad' : 'bg-ok'"
            ></span>
            <span class="flex min-w-0 flex-1 flex-col gap-1">
              <span class="truncate font-mono text-[calc(11.5px*var(--fs))] text-accent">
                {{ relayDeliveryLabel(delivery) }}
              </span>
              <span class="h-[7px] w-[106px] rounded bg-line-soft"></span>
            </span>
          </div>
        </div>
      </PanelCard>
    </aside>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import PanelCard from '@/components/ui/PanelCard.vue'
import DetailStatusCard from './DetailStatusCard.vue'
import { useChatRowFields } from '@/composables/useChatRowFields'
import { useRelayDeliveries } from '@/composables/useRelayDeliveries'
import { usePreferencesStore } from '@/store/preferences'
import { formatDate } from '@/utils/timezone'

const props = defineProps({
  // The list row this panel was opened from. Everything drawn for real
  // comes from here; everything else is a placeholder.
  seed: { type: Object, required: true },
  variant: { type: String, default: 'drawer' }
})

const { t } = useI18n()
const preferences = usePreferencesStore()
const { relayDeliveryLabel, relayDeliveryKey, getRelayDeliveries } =
  useRelayDeliveries()

const { status, percent, title, senderName, mergedCount, tags } =
  useChatRowFields(() => props.seed)

const deliveries = computed(() => getRelayDeliveries(props.seed))

const attachmentCount = computed(
  () => props.seed?.attachments_count ?? props.seed?.attachments?.length ?? 0
)

// The list row shows a short stamp; the panel has room for the full one.
const receivedAt = computed(() => {
  const raw = props.seed?.received_at || props.seed?.created_at
  if (!raw) return t('common.noData')
  return formatDate(
    raw,
    preferences.currentTimezone,
    'yyyy-MM-dd HH:mm',
    preferences.currentLanguage
  )
})

const LABELS = {
  success: 'chats.stateCompleted',
  processing: 'chats.stateProcessing',
  retrying: 'chats.stateProcessing',
  failed: 'chats.stateFailed',
  fetched: 'chats.statePending'
}
const statusLabel = computed(() => {
  const label = t(LABELS[status.value] || 'common.status.unknown')
  return percent.value === null ? label : `${label} ${percent.value}%`
})
const statusChipClass = computed(
  () =>
    ({
      success: 'bg-ok-soft text-ok',
      processing: 'bg-warn-soft text-warn',
      retrying: 'bg-warn-soft text-warn',
      failed: 'bg-bad-soft text-bad',
      fetched: 'bg-chip text-ink-2'
    })[status.value] || 'bg-chip text-ink-2'
)

const disclosureLabels = computed(() => [
  t('chats.detail.originalEmails'),
  t('chats.detail.aiOutput')
])

// Fixed proportions rather than random ones, so the placeholder does not
// change shape between two renders of the same wait.
const SUMMARY_LINES = ['97%', '93%', '96%', '51%']
const TODO_ROWS = [
  ['74%', '31%'],
  ['62%', '27%'],
  ['55%', '24%']
]
const PROCESS_LINES = ['64%', '78%', '57%']
const TILES = [
  { name: '82%', size: '44%', opacity: 1 },
  { name: '70%', size: '38%', opacity: 0.7 },
  { name: '76%', size: '41%', opacity: 0.45 }
]
const attachmentTiles = computed(() =>
  TILES.slice(0, Math.min(3, attachmentCount.value)).map((tile, index) => ({
    ...tile,
    key: index
  }))
)

// The two fields the loaded card actually carries. The artboard also draws
// 场景 and 项目, which this build has no field for.
const INFO_FIELDS = [
  { label: 'metadata.category.title', width: '76px' },
  { label: 'metadata.participants.title', width: '108px' }
]
</script>
