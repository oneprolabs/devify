<template>
  <AppLayout :padded="false">
    <!-- Configuring a channel takes over the header: the page is about that
         channel then, and its test and save belong at the top. -->
    <PageHeader
      v-if="selectedChannel"
      :parent="{ to: '/apps/relay', label: t('relay.pageTitle') }"
      :title="selectedChannel.name"
    >
      <span
        class="rounded-sm px-[7px] py-0.5 font-mono text-[calc(10.5px*var(--fs))]"
        :class="
          selectedChannel.enabled ? 'bg-ok-soft text-ok' : 'bg-chip text-ink-3'
        "
      >
        {{
          selectedChannel.enabled
            ? t('relay.channelEnabled')
            : t('relay.channelDisabled')
        }}
      </span>

      <div class="ml-auto flex items-center gap-2">
        <button
          type="button"
          class="font-display flex h-8 items-center gap-[7px] rounded-md border border-line px-[13px] text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:border-ink-4 disabled:opacity-50"
          :disabled="editor.testing.value || editor.saving.value"
          @click="editor.runEditorTest"
        >
          <svg
            class="h-[13px] w-[13px]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            aria-hidden="true"
          >
            <path d="M7 5l11 7-11 7V5z" stroke-linejoin="round" />
          </svg>
          {{ t('relay.runTest') }}
        </button>
        <button
          type="button"
          class="font-display flex h-8 items-center rounded-md bg-accent px-[15px] text-[calc(12.5px*var(--fs))] font-medium text-accent-on transition-opacity hover:opacity-90 disabled:opacity-40"
          :disabled="
            editor.saving.value ||
            editor.testing.value ||
            !editor.editorCanSave.value
          "
          @click="editor.saveEditor"
        >
          {{ t('relay.saveTargets') }}
        </button>
      </div>
    </PageHeader>

    <PageHeader
      v-else
      :parent="{ to: '/apps', label: t('apps.centerTitle') }"
      :title="t('relay.pageTitle')"
    >
      <label
        class="flex h-8 max-w-[362px] flex-1 items-center gap-2 rounded-md border border-line bg-panel-sub px-2.5"
      >
        <svg
          class="h-3.5 w-3.5 flex-none text-ink-3"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-4.5-4.5" stroke-linecap="round" />
        </svg>
        <input
          v-model="search"
          type="text"
          :placeholder="t('relay.searchPlaceholder')"
          class="min-w-0 flex-1 border-0 bg-transparent p-0 text-[calc(12.5px*var(--fs))] text-ink placeholder:text-ink-3 focus:outline-none focus:ring-0"
        />
      </label>

      <div class="ml-auto flex items-center gap-[7px]">
        <FilterSelect
          :label="channelFilterLabel"
          :options="channelOptions"
          :model-value="channelFilter"
          @update:model-value="channelFilter = $event"
        />
        <FilterSelect
          :label="statusFilterLabel"
          :options="statusOptions"
          :model-value="statusFilter"
          @update:model-value="statusFilter = $event"
        />
        <button
          v-if="failedCount"
          type="button"
          class="font-display flex h-8 items-center gap-[7px] rounded-md border border-bad px-[13px] text-[calc(12.5px*var(--fs))] text-bad transition-colors hover:bg-bad-soft"
          @click="retryAllDeliveries"
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
              d="M20 12a8 8 0 11-2.6-5.9M20 4v4.5h-4.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          {{ t('relay.retryAllFailed', { count: failedCount }) }}
        </button>
      </div>
    </PageHeader>

    <!-- Two views of the same app: what went out, and where it can go. -->
    <div
      class="flex h-11 flex-shrink-0 items-center gap-[26px] border-b border-line px-4 md:px-5"
    >
      <button
        v-for="tab in tabs"
        :key="tab.value"
        type="button"
        class="font-display flex h-11 items-center text-[calc(13px*var(--fs))] transition-colors"
        :class="
          activeTab === tab.value
            ? '-mb-px border-b-2 border-accent font-semibold text-accent'
            : 'font-medium text-ink-3 hover:text-ink-2'
        "
        role="tab"
        :aria-selected="activeTab === tab.value"
        @click="activeTab = tab.value"
      >
        {{ tab.label }}
        <span
          v-if="tab.count"
          class="ml-[7px] font-mono text-[calc(10.5px*var(--fs))] text-ink-4"
        >
          {{ tab.count }}
        </span>
      </button>
    </div>

    <RelayStatStrip
      v-if="activeTab === 'deliveries'"
      :total="stats.total"
      :this-week="stats.deliveries_this_week"
      :failed="stats.failed"
      :success-rate="stats.success_rate"
      :by-channel="stats.by_channel"
    />

    <template v-if="activeTab === 'deliveries'">
      <div
        class="hidden h-8 flex-shrink-0 items-center gap-[14px] border-b border-line bg-panel-sub px-5 font-mono text-[calc(10.5px*var(--fs))] tracking-[0.06em] text-ink-4 md:flex"
      >
        <div class="w-20 flex-none">{{ t('relay.colStatus') }}</div>
        <div class="min-w-0 flex-1">{{ t('relay.colSource') }}</div>
        <div class="w-[196px] flex-none">{{ t('relay.colChannel') }}</div>
        <div class="w-28 flex-none">{{ t('relay.colTarget') }}</div>
        <div class="w-24 flex-none text-right">{{ t('relay.colTime') }}</div>
        <div class="w-[62px] flex-none"></div>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto">
        <SkeletonRows v-if="loading" :count="5" />

        <p
          v-else-if="!deliveryRows.length"
          class="py-16 text-center text-sm italic text-ink-3"
        >
          {{ t('relay.noDeliveries') }}
        </p>

        <template v-else>
          <DeliveryRow
            v-for="row in deliveryRows"
            :key="row.key"
            :delivery="row"
            :busy="isEventRetryBusy(row.event)"
            @retry="retrySelectedDelivery(row.event, row.id)"
          />
          <div
            v-if="deliveryPagination.hasMore"
            class="flex justify-center p-4"
          >
            <button
              ref="deliveryLoadMoreSentinel"
              type="button"
              class="rounded-md border border-line px-4 py-1.5 text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:border-ink-4"
              :disabled="loadingMoreDeliveries"
              @click="deliveryList.loadDeliveries(true)"
            >
              {{
                loadingMoreDeliveries
                  ? t('common.loading')
                  : t('common.loadMore')
              }}
            </button>
          </div>
        </template>
      </div>
    </template>

    <!-- Channels are a master-detail: the rail lists what exists, the panel
         beside it configures the one selected. Creating starts a step
         further back, at the type gallery. -->
    <div
      v-else
      class="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row"
    >
      <ChannelRail
        :channels="subscriptions"
        :selected-id="expandedSubscriptionId"
        @select="editSubscription"
        @toggle="toggleSubscriptionEnabled"
        @create="startCreate"
      />

      <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <template v-if="editorVisible && editorMode === 'create'">
          <div
            class="flex h-14 flex-shrink-0 items-center gap-0 overflow-x-auto border-b border-line px-4 md:px-6"
          >
            <template v-for="(step, index) in createSteps" :key="step.key">
              <span
                v-if="index"
                class="mx-4 h-px w-14 flex-none bg-line"
              ></span>
              <span class="flex flex-none items-center gap-[9px]">
                <span
                  class="flex h-[22px] w-[22px] items-center justify-center rounded-full font-mono text-[calc(11px*var(--fs))]"
                  :class="
                    step.done
                      ? 'bg-accent font-medium text-accent-on'
                      : 'border border-line text-ink-4'
                  "
                >
                  {{ index + 1 }}
                </span>
                <span
                  class="font-display text-[calc(13px*var(--fs))]"
                  :class="
                    step.done ? 'font-semibold text-accent' : 'text-ink-3'
                  "
                >
                  {{ step.label }}
                </span>
              </span>
            </template>

            <button
              type="button"
              class="font-display ml-auto flex h-8 flex-none items-center rounded-md border border-line px-[13px] text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:border-ink-4"
              @click="cancelEditor"
            >
              {{ t('common.cancel') }}
            </button>
          </div>

          <div class="min-h-0 flex-1 overflow-y-auto">
            <ChannelTypePicker
              v-if="!editorForm.target_type"
              v-model="editorForm.target_type"
              :channels="subscriptions"
            />
            <div v-else class="p-4 md:p-6">
              <ChannelEditor :editor="editor" />
            </div>
          </div>
        </template>

        <!-- `editSubscription` marks the row rather than opening a panel;
             in a master-detail that mark is what selects the editor. -->
        <div
          v-else-if="expandedSubscriptionId"
          class="min-h-0 flex-1 overflow-y-auto p-4 md:p-6"
        >
          <ChannelEditor :editor="editor" />
        </div>

        <p
          v-else
          class="flex flex-1 items-center justify-center p-8 text-center text-sm italic text-ink-3"
        >
          {{
            subscriptions.length
              ? t('relay.pickChannel')
              : t('relay.noSubscriptions')
          }}
        </p>
      </div>
    </div>

    <ConfirmDialog
      :show="retryConfirm.show"
      :title="retryConfirm.title"
      :message="retryConfirm.message"
      :confirm-text="retryConfirm.confirmText"
      variant="warning"
      @close="closeRetryConfirm"
      @confirm="confirmRetry"
    >
      <div
        class="mt-3 rounded-lg border border-warn bg-warn-soft p-3 text-sm text-warn"
      >
        {{ retryConfirm.note }}
      </div>
    </ConfirmDialog>
  </AppLayout>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import FilterSelect from '@/components/ui/FilterSelect.vue'
import DeliveryRow from '@/components/relay/DeliveryRow.vue'
import RelayStatStrip from '@/components/relay/RelayStatStrip.vue'
import ChannelRail from '@/components/relay/ChannelRail.vue'
import ChannelEditor from '@/components/relay/ChannelEditor.vue'
import ChannelTypePicker from '@/components/relay/ChannelTypePicker.vue'
import SkeletonRows from '@/components/ui/SkeletonRows.vue'
import { relayApi } from '@/api/relay'
import { useRelayFormatters } from '@/composables/useRelayFormatters'
import { useRelayDeliveryList } from '@/composables/useRelayDeliveryList'
import { useRelayRetry } from '@/composables/useRelayRetry'
import { useRelayEditor } from '@/composables/useRelayEditor'

const { t } = useI18n()

const activeTab = ref('deliveries')
const subscriptions = ref([])

async function loadSubscriptions() {
  const data = await relayApi.getSubscriptions()
  subscriptions.value = Array.isArray(data) ? data : []
}

const tabs = computed(() => [
  { value: 'deliveries', label: t('relay.tabsDeliveries') },
  {
    value: 'channels',
    label: t('relay.tabsChannels'),
    count: subscriptions.value.length
  }
])

const stats = ref({
  total: 0,
  deliveries_this_week: 0,
  failed: 0,
  success_rate: 0,
  by_channel: {}
})

async function loadStats() {
  try {
    const data = await relayApi.getStats()
    if (data) stats.value = { ...stats.value, ...data }
  } catch (error) {
    console.error('Failed to load relay stats:', error)
  }
}

const search = ref('')
const channelFilter = ref('')
const statusFilter = ref('')

const channelOptions = computed(() => [
  { value: '', label: t('relay.allChannels') },
  { value: 'feishu_bitable', label: t('relay.targetFeishu') },
  { value: 'jira', label: t('relay.targetJira') },
  { value: 'github_issue', label: t('relay.targetGitHub') }
])
const statusOptions = computed(() => [
  { value: '', label: t('todos.filters.all') },
  { value: 'success', label: t('common.status.success') },
  { value: 'failed', label: t('common.status.failed') },
  { value: 'processing', label: t('common.status.processing') },
  { value: 'pending', label: t('common.status.pending') }
])
// The option label already reads as the field ("all channels", or the
// channel's own name), so the canvas shows it without a prefix.
const channelFilterLabel = computed(
  () =>
    channelOptions.value.find((o) => o.value === channelFilter.value)?.label ||
    ''
)
const statusFilterLabel = computed(() =>
  t('relay.statusFilter', {
    name:
      statusOptions.value.find((o) => o.value === statusFilter.value)?.label ||
      ''
  })
)

const failedCount = computed(() => stats.value.failed || 0)

const selectedChannel = computed(() => {
  if (activeTab.value !== 'channels' || !expandedSubscriptionId.value) {
    return null
  }
  return (
    subscriptions.value.find(
      (sub) => String(sub.id) === String(expandedSubscriptionId.value)
    ) || null
  )
})

// Creating a channel is three steps; the type gallery is the first, and the
// editor's own test is the last.
const createSteps = computed(() => [
  { key: 'type', label: t('relay.stepPickType'), done: true },
  {
    key: 'configure',
    label: t('relay.stepConfigure'),
    done: Boolean(editorForm.target_type)
  },
  {
    key: 'test',
    label: t('relay.stepTest'),
    done: Boolean(editorTestPassed.value)
  }
])

// The gallery decides the type, so a new channel starts without one.
function startCreate() {
  openCreatePanel()
  editorForm.target_type = ''
}

const deliveryList = useRelayDeliveryList({ loadSubscriptions, activeTab })
const {
  loading,
  deliveries,
  deliveryPagination,
  deliveryLoadMoreSentinel,
  loadingMoreDeliveries,
  retrySelection,
  reloadAll,
  disconnectDeliveryLoadMoreObserver,
  refreshDeliveryLoadMoreObserver
} = deliveryList

const retry = useRelayRetry({
  retrySelection,
  deliveryPagination,
  loadDeliveries: deliveryList.loadDeliveries,
  findEventByDeliveryId: deliveryList.findEventByDeliveryId,
  markEventProcessing: deliveryList.markEventProcessing,
  activeTab
})

const editor = useRelayEditor({ reloadAll, activeTab })
const formatters = useRelayFormatters()

// Export retry functions and state used in template
const {
  retryConfirm,
  isEventRetryBusy,
  confirmRetry,
  closeRetryConfirm,
  retryAllDeliveries,
  retrySelectedDelivery
} = retry

// The editor panel draws the rest of the editor's state itself.
const {
  editorVisible,
  editorMode,
  expandedSubscriptionId,
  editorForm,
  editorTestPassed,
  openCreatePanel,
  cancelEditor,
  editSubscription,
  toggleSubscriptionEnabled
} = editor

const { eventDeliveries } = formatters

// The canvas logs one row per delivery. Events carry theirs nested, so they
// are flattened here and filtered by what the header offers.
const deliveryRows = computed(() => {
  const term = search.value.trim().toLowerCase()

  return deliveries.value.flatMap((event) =>
    eventDeliveries(event)
      .map((delivery) => ({
        ...delivery,
        event,
        key: `${event.id}:${delivery.id}`,
        event_artifact_snapshot:
          delivery.event_artifact_snapshot || event.artifact_snapshot
      }))
      .filter((row) => {
        if (channelFilter.value && row.target_type !== channelFilter.value) {
          return false
        }
        if (statusFilter.value && row.status !== statusFilter.value) {
          return false
        }
        if (!term) return true

        const snapshot = row.event_artifact_snapshot || {}
        return [
          snapshot.summary_title,
          snapshot.subject,
          row.external_id,
          row.subscription?.name
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(term))
      })
  )
})

watch(activeTab, async (value) => {
  if (value === 'deliveries') {
    await nextTick()
    refreshDeliveryLoadMoreObserver()
  } else {
    disconnectDeliveryLoadMoreObserver()
  }
})

onMounted(async () => {
  await Promise.all([reloadAll(), loadStats()])
})

onBeforeUnmount(() => {
  disconnectDeliveryLoadMoreObserver()
  retry.cancelAllPolls()
})
</script>
