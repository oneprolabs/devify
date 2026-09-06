<template>
  <AppLayout :padded="false">
    <!-- Opening a conversation slides the panel in from the right and leaves
         the list in place — no scrim, so the next row is still one click
         away. Below `lg` there is no room for both, and the panel takes the
         screen on its own. -->
    <!-- Too narrow for both: the conversation takes the screen on its own,
         which is also where a resize past the threshold lands. -->
    <ThreadlineDetailPanel
      v-if="openId && !isWide"
      variant="page"
      :seed="openRow"
    />

    <div v-else-if="drawerOpen" class="flex min-h-0 flex-1 overflow-hidden">
      <div
        class="flex w-[328px] flex-none flex-col overflow-hidden border-r border-line"
      >
        <div
          class="flex h-14 flex-shrink-0 items-center gap-2 border-b border-line px-3.5"
        >
          <span class="text-[calc(13.5px*var(--fs))] font-semibold text-ink">
            {{ t('chats.title') }}
          </span>
          <span class="font-mono text-[calc(10.5px*var(--fs))] text-ink-3">
            {{ pagination.total }}
          </span>
          <div class="ml-auto flex items-center gap-1.5">
            <button
              type="button"
              class="flex h-7 w-7 items-center justify-center rounded-md border border-line text-ink-2 transition-colors hover:border-ink-4"
              :aria-label="t('common.search')"
              @click="railSearchOpen = !railSearchOpen"
            >
              <svg
                class="h-3.5 w-3.5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-4.5-4.5" stroke-linecap="round" />
              </svg>
            </button>
            <button
              type="button"
              class="flex h-7 w-7 items-center justify-center rounded-md border border-line transition-colors hover:border-ink-4"
              :class="hasFilters ? 'text-accent' : 'text-ink-2'"
              :aria-label="t('chats.statusAll')"
              @click="cycleStatusFilter"
            >
              <svg
                class="h-3.5 w-3.5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <path d="M4 6h16M7 12h10M10 18h4" stroke-linecap="round" />
              </svg>
            </button>
          </div>
        </div>

        <div v-if="railSearchOpen" class="border-b border-line px-3.5 py-2">
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t('chats.searchHint')"
            class="h-8 w-full rounded-md border border-line bg-panel-sub px-2.5 text-[calc(12.5px*var(--fs))] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none focus:ring-0"
          />
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto">
          <SkeletonRows v-if="loading" :count="6" />
          <ChatRailCard
            v-for="chat in results"
            v-else
            :key="chat.uuid || chat.id"
            :chat="chat"
            :active="String(chat.uuid) === String(openId)"
            @open="viewResult"
          />
        </div>

        <div
          class="flex h-11 flex-shrink-0 items-center justify-between border-t border-line px-3.5"
        >
          <span class="font-mono text-[calc(10.5px*var(--fs))] text-ink-3">
            {{ railRangeLabel }}
          </span>
          <div class="flex items-center gap-1.5">
            <button
              type="button"
              class="rounded-md border border-line px-[9px] py-1 font-mono text-[calc(10.5px*var(--fs))] transition-colors"
              :class="
                pagination.page > 1
                  ? 'text-ink hover:border-ink-4'
                  : 'cursor-not-allowed text-ink-4'
              "
              :disabled="pagination.page <= 1"
              @click="goToPage(pagination.page - 1)"
            >
              {{ t('chats.prevPage') }}
            </button>
            <button
              type="button"
              class="rounded-md border border-line px-[9px] py-1 font-mono text-[calc(10.5px*var(--fs))] transition-colors"
              :class="
                pagination.hasMore
                  ? 'text-ink hover:border-ink-4'
                  : 'cursor-not-allowed text-ink-4'
              "
              :disabled="!pagination.hasMore"
              @click="goToPage(pagination.page + 1)"
            >
              {{ t('chats.nextPage') }}
            </button>
          </div>
        </div>
      </div>

      <div
        class="flex min-w-0 flex-1 flex-col overflow-hidden border-l border-line bg-panel shadow-[-14px_0_34px_rgba(9,14,26,0.10)]"
      >
        <ThreadlineDetailPanel
          ref="detailPanel"
          variant="drawer"
          :seed="openRow"
          :position="drawerPosition"
          :has-prev="drawerIndex > 0"
          :has-next="drawerIndex >= 0 && drawerIndex < results.length - 1"
          @close="closeDrawer"
          @prev="stepDrawer(-1)"
          @next="stepDrawer(1)"
        />
      </div>
    </div>

    <template v-else>
      <PageHeader :title="t('chats.title')" :count="totalLabel">
        <ChatToolbar
          v-model:search="searchQuery"
          v-model:status="statusFilter"
          v-model:range="rangeFilter"
          :selected-count="selectedCount"
          :loading="loading"
          @merge="openMergeConfirm"
          @refresh="refreshData"
        />

        <template #mobile>
          <button
            type="button"
            class="text-ink-2"
            :aria-label="t('common.search')"
            @click="mobileSearchOpen = !mobileSearchOpen"
          >
            <svg
              class="h-[19px] w-[19px]"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-4.5-4.5" stroke-linecap="round" />
            </svg>
          </button>
          <button
            type="button"
            :class="selectionMode ? 'text-accent' : 'text-ink-2'"
            :aria-label="t('chats.bulkMerge.selectMode')"
            @click="toggleSelectionMode"
          >
            <svg
              class="h-[19px] w-[19px]"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <path
                d="M8 6h12M8 12h12M8 18h12M3.5 6h.01M3.5 12h.01M3.5 18h.01"
                stroke-linecap="round"
              />
            </svg>
          </button>
        </template>
      </PageHeader>

      <div
        v-if="mobileSearchOpen"
        class="border-b border-line px-4 py-2 md:hidden"
      >
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="t('chats.searchHint')"
          class="h-9 w-full rounded-md border border-line bg-panel-sub px-3 text-[calc(13px*var(--fs))] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none focus:ring-0"
        />
      </div>

      <ChatStatStrip
        :total="stats.total"
        :this-week="stats.thisWeek"
        :pending="stats.pending"
        :completed="stats.completed"
        :virtual-email="userStore.userInfo?.virtual_email || ''"
      />

      <!-- On a phone the status filter is a row of chips rather than a menu. -->
      <div
        class="flex h-11 flex-shrink-0 items-center gap-1.5 overflow-x-auto border-b border-line px-4 md:hidden"
      >
        <button
          v-for="chip in statusChips"
          :key="chip.value"
          type="button"
          class="font-display flex-none rounded-md px-3 py-1.5 text-xs transition-colors"
          :class="
            statusFilter === chip.value
              ? 'bg-accent font-medium text-accent-on'
              : 'border border-line text-ink-2'
          "
          @click="statusFilter = chip.value"
        >
          {{ chip.label }}
        </button>
      </div>

      <!-- Desktop column headings, matching the row widths below. -->
      <div
        class="hidden h-[33px] flex-shrink-0 items-center gap-[14px] border-b border-line bg-panel-sub px-5 font-mono text-[calc(10.5px*var(--fs))] tracking-[0.06em] text-ink-4 md:flex"
      >
        <div class="w-[15px] flex-none"></div>
        <div class="w-[92px] flex-none">{{ t('chats.colStatus') }}</div>
        <div class="min-w-0 flex-1">{{ t('chats.colTitle') }}</div>
        <div class="w-[130px] flex-none">{{ t('chats.colTags') }}</div>
        <div class="w-[150px] flex-none">{{ t('chats.colSource') }}</div>
        <div class="w-[108px] flex-none">{{ t('chats.colRelay') }}</div>
        <div class="w-[88px] flex-none text-right">
          {{ t('chats.colTime') }}
        </div>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto">
        <SkeletonRows v-if="loading" :count="6" />

        <!-- Nothing yet and nothing found are different problems: one needs the
             mailbox address, the other needs the filters loosened. -->
        <EmptyState
          v-else-if="!results.length && hasFilters"
          :title="t('chats.noResults')"
          :description="t('chats.noResultsBody')"
        >
          <template #icon>
            <svg
              class="h-6 w-6"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-4.5-4.5" stroke-linecap="round" />
            </svg>
          </template>
          <button
            type="button"
            class="font-display text-xs text-accent hover:underline"
            @click="clearFilters"
          >
            {{ t('todos.filters.clearAll') }}
          </button>
        </EmptyState>

        <EmptyState
          v-else-if="!results.length"
          :title="t('chats.emptyTitle')"
          :description="t('chats.emptyBody')"
        >
          <template #icon>
            <svg
              class="h-6 w-6"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              aria-hidden="true"
            >
              <rect x="2.5" y="4.5" width="19" height="15" rx="2.5" />
              <path
                d="M3 7l9 6 9-6"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </template>

          <VirtualEmailBanner
            v-if="userStore.userInfo?.virtual_email"
            :virtual-email="userStore.userInfo.virtual_email"
            :label="t('chats.mailboxLabel')"
          />
          <router-link
            to="/settings"
            class="font-display text-xs text-accent hover:underline"
          >
            {{ t('chats.emptyConnectImap') }}
          </router-link>
        </EmptyState>

        <template v-else>
          <ChatRow
            v-for="chat in results"
            :key="chat.uuid || chat.id"
            class="hidden md:flex"
            :chat="chat"
            :selected="selectedIds.includes(chat.uuid)"
            @open="viewResult"
            @toggle="toggleSelection"
            @retry="openRetryFor"
          />
          <ChatCard
            v-for="chat in results"
            :key="`m-${chat.uuid || chat.id}`"
            class="md:hidden"
            :chat="chat"
            :selectable="selectionMode"
            :selected="selectedIds.includes(chat.uuid)"
            @open="selectionMode ? toggleSelection(chat) : viewResult(chat)"
            @toggle="toggleSelection"
          />
        </template>
      </div>

      <ChatPager
        v-if="!loading && results.length"
        :page="pagination.page"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        :count="results.length"
        :has-more="pagination.hasMore"
        @update:page="goToPage"
      />

      <ConfirmDialog
        :show="showMergeConfirm"
        :title="t('chats.bulkMerge.confirmTitle')"
        :message="mergeConfirmMessage"
        :confirm-text="t('chats.bulkMerge.merge')"
        variant="primary"
        :loading="mergeLoading"
        @close="showMergeConfirm = false"
        @confirm="confirmMerge"
      >
        <div
          v-if="selectedThreadlines.length > 0"
          class="mt-4 rounded-lg border border-line bg-app-sub p-3"
        >
          <div class="mb-2 text-xs font-medium text-ink-3">
            {{ t('chats.bulkMerge.selectedItems') }}
          </div>
          <div class="space-y-2">
            <div
              v-for="item in selectedThreadlines"
              :key="item.uuid"
              class="rounded-md border border-line bg-panel px-3 py-2"
            >
              <div class="truncate text-sm font-medium text-ink">
                {{ item.summary_title || item.subject || `Email #${item.id}` }}
              </div>
            </div>
          </div>
        </div>
        <div class="mt-4 space-y-2">
          <label class="block text-sm font-medium text-ink-2">
            {{ t('chats.bulkMerge.noteLabel') }}
          </label>
          <textarea
            v-model="mergeNote"
            rows="3"
            maxlength="100"
            class="w-full rounded-md border border-line px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent"
            :placeholder="t('chats.bulkMerge.notePlaceholder')"
          ></textarea>
          <div class="text-xs text-ink-3">
            {{
              t('chats.bulkMerge.noteHint', {
                count: mergeNote.length,
                max: 100
              })
            }}
          </div>
        </div>
      </ConfirmDialog>

      <RetryDialog
        :show="showRetryDialog"
        :status="retryDialogStatus"
        @close="showRetryDialog = false"
        @confirm="handleRetryConfirm"
      />

      <!-- The phone has no toolbar to hold the merge button, so selection
           raises its own bar above the tab bar. -->
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="translate-y-4 opacity-0"
        leave-active-class="transition duration-150 ease-in"
        leave-to-class="translate-y-4 opacity-0"
      >
        <div
          v-if="selectedCount > 0"
          class="fixed inset-x-3 bottom-[70px] z-40 flex items-center gap-3 rounded-lg border border-accent bg-panel/95 px-3 py-2.5 shadow-soft-lg backdrop-blur md:hidden"
        >
          <span class="text-[calc(13px*var(--fs))] text-ink">
            {{ t('chats.bulkMerge.selectedCount', { count: selectedCount }) }}
          </span>
          <button
            type="button"
            class="ml-auto text-[calc(13px*var(--fs))] text-ink-3"
            @click="clearSelection"
          >
            {{ t('chats.bulkMerge.clear') }}
          </button>
          <button
            type="button"
            class="rounded-md bg-accent px-3 py-1.5 text-[calc(13px*var(--fs))] font-medium text-accent-on disabled:opacity-50"
            :disabled="selectedCount < 2 || mergeLoading"
            @click="openMergeConfirm"
          >
            {{ t('chats.bulkMerge.merge') }}
          </button>
        </div>
      </Transition>
    </template>
  </AppLayout>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { chatApi } from '@/api/chat'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import ChatToolbar from '@/components/chats/ChatToolbar.vue'
import ChatStatStrip from '@/components/chats/ChatStatStrip.vue'
import ChatRow from '@/components/chats/ChatRow.vue'
import ChatCard from '@/components/chats/ChatCard.vue'
import ChatPager from '@/components/chats/ChatPager.vue'
import ChatRailCard from '@/components/chats/ChatRailCard.vue'
import ThreadlineDetailPanel from '@/components/threadline/detail/ThreadlineDetailPanel.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonRows from '@/components/ui/SkeletonRows.vue'
import VirtualEmailBanner from '@/components/ui/VirtualEmailBanner.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import RetryDialog from '@/components/RetryDialog.vue'
import { useToast } from '@/composables/useToast'
import { getThreadlineDisplayStatus } from '@/utils/threadlineStatus'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const toast = useToast()

const MAX_MERGE_COUNT = 5
const POLL_INTERVAL_MS = 2000

const loading = ref(false)
const mergeLoading = ref(false)
const showMergeConfirm = ref(false)
const showRetryDialog = ref(false)
const retryTargets = ref([])
const mergeNote = ref('')
const searchQuery = ref('')
const statusFilter = ref('')
const rangeFilter = ref('30')
const mobileSearchOpen = ref(false)
const selectionMode = ref(false)
const results = ref([])
const selectedIds = ref([])
const pagination = ref({ page: 1, pageSize: 20, total: 0, hasMore: false })
const stats = ref({ total: 0, thisWeek: 0, pending: 0, completed: 0 })

let pollTimer = null
let searchTimer = null
let isActive = true

const totalLabel = computed(() =>
  pagination.value.total
    ? t('chats.countUnit', {
        count: new Intl.NumberFormat('en-US').format(pagination.value.total)
      })
    : null
)
const selectedCount = computed(() => selectedIds.value.length)
const selectedThreadlines = computed(() =>
  results.value.filter((item) => selectedIds.value.includes(item.uuid))
)
const hasFilters = computed(
  () => Boolean(searchQuery.value.trim()) || Boolean(statusFilter.value)
)
const statusChips = computed(() => [
  { value: '', label: t('chats.filterAll') },
  { value: 'fetched', label: t('chats.statePending') },
  { value: 'processing', label: t('chats.stateProcessing') },
  { value: 'failed', label: t('chats.stateFailed') }
])
const activeThreadlineIds = computed(() =>
  results.value
    .filter((item) => {
      const status = getThreadlineDisplayStatus(item)
      return status === 'processing' || status === 'retrying'
    })
    .map((item) => item.uuid || item.id)
    .filter(Boolean)
)
const retryDialogStatus = computed(() =>
  retryTargets.value.some((item) => item.status === 'success')
    ? 'success'
    : 'failed'
)
const mergeConfirmMessage = computed(() => {
  const titles = selectedThreadlines.value
    .map((item) => item.summary_title || item.subject || `Email #${item.id}`)
    .slice(0, 3)

  if (!titles.length) return t('chats.bulkMerge.confirmMessage')

  const suffix = selectedCount.value > titles.length ? '...' : ''
  return `${t('chats.bulkMerge.confirmMessage')} ${titles.join('、')}${suffix}`
})

// The range control offers whole days back from now; "" means all time.
const receivedAfter = computed(() => {
  const days = Number(rangeFilter.value)
  if (!days) return null
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString()
})

const loadData = async () => {
  if (!isActive) return
  // The narrow detail screen shows no list, so it fetches none.
  if (openId.value && !isWide.value) return

  loading.value = true
  selectedIds.value = []

  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize
    }
    if (searchQuery.value.trim()) params.search = searchQuery.value.trim()
    if (statusFilter.value) params.status = statusFilter.value
    if (receivedAfter.value) params.received_after = receivedAfter.value

    const response = await chatApi.getThreadlines(params)
    const data = response.data.data || response.data
    results.value = data.list || data.results || []

    if (data.pagination) {
      pagination.value = {
        page: data.pagination.page || pagination.value.page,
        pageSize: data.pagination.pageSize || pagination.value.pageSize,
        total: data.pagination.total || 0,
        hasMore:
          data.pagination.next !== null && data.pagination.next !== undefined
      }
    }
  } catch (error) {
    console.error('Failed to load threadlines:', error)
  } finally {
    loading.value = false
    syncPolling()
  }
}

const loadStats = async () => {
  try {
    const response = await chatApi.getThreadlineStats()
    const data = response.data.data || response.data
    stats.value = {
      total: data.total || 0,
      thisWeek: data.this_week || 0,
      pending: data.pending || 0,
      completed: data.completed || 0
    }
  } catch (error) {
    console.error('Failed to load threadline stats:', error)
  }
}

const refreshData = () => {
  loadData()
  loadStats()
}

// --- The right-hand drawer -------------------------------------------------

// Below this the rail and the panel cannot both fit, so /chats/:id is a page
// of its own instead. The canvas puts the line at 1180px.
const WIDE = window.matchMedia('(min-width: 1180px)')
const isWide = ref(WIDE.matches)
const syncWide = (event) => {
  isWide.value = event.matches
}

const openId = computed(() => route.params.id || '')
const drawerOpen = computed(() => Boolean(openId.value) && isWide.value)
const railSearchOpen = ref(false)

const drawerIndex = computed(() =>
  results.value.findIndex((chat) => String(chat.uuid) === String(openId.value))
)
// The row the panel was opened from, so the wait can draw what the list
// already knows instead of an empty panel.
const openRow = computed(() =>
  drawerIndex.value < 0 ? null : results.value[drawerIndex.value]
)

const drawerPosition = computed(() => {
  if (drawerIndex.value < 0) return null
  return {
    index:
      (pagination.value.page - 1) * pagination.value.pageSize +
      drawerIndex.value +
      1,
    total: pagination.value.total
  }
})
const railRangeLabel = computed(() =>
  t('chats.showingRange', {
    from: results.value.length
      ? (pagination.value.page - 1) * pagination.value.pageSize + 1
      : 0,
    to:
      (pagination.value.page - 1) * pagination.value.pageSize +
      results.value.length,
    total: pagination.value.total
  })
)

const detailPanel = ref(null)
const closeDrawer = () => router.push('/chats')

// The panel commits an open edit first, so Escape and the × behave alike.
const requestCloseDrawer = () => {
  if (detailPanel.value?.requestClose) {
    detailPanel.value.requestClose()
    return
  }
  closeDrawer()
}

const stepDrawer = (delta) => {
  const next = results.value[drawerIndex.value + delta]
  if (next) viewResult(next)
}

// J and K move through the list the way a mail client does; Escape closes.
const handleDrawerKeys = (event) => {
  if (!drawerOpen.value) return
  const tag = event.target?.tagName
  if (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    event.target?.isContentEditable
  ) {
    return
  }
  if (event.key === 'Escape') {
    requestCloseDrawer()
  } else if (event.key === 'j' || event.key === 'J') {
    stepDrawer(1)
  } else if (event.key === 'k' || event.key === 'K') {
    stepDrawer(-1)
  }
}

// The rail has no room for a status menu, so its filter button cycles.
const cycleStatusFilter = () => {
  const order = ['', 'fetched', 'processing', 'failed', 'success']
  const at = order.indexOf(statusFilter.value)
  statusFilter.value = order[(at + 1) % order.length]
}

const clearFilters = () => {
  searchQuery.value = ''
  statusFilter.value = ''
  rangeFilter.value = ''
}

const goToPage = (page) => {
  pagination.value.page = Math.max(1, page)
  loadData()
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const syncPolling = () => {
  if (!activeThreadlineIds.value.length) {
    stopPolling()
    return
  }
  if (pollTimer) return

  pollTimer = setInterval(async () => {
    if (loading.value || !activeThreadlineIds.value.length) return
    await refreshRows(activeThreadlineIds.value)
  }, POLL_INTERVAL_MS)
}

const refreshRows = async (ids) => {
  try {
    await Promise.all(
      ids.map(async (id) => {
        try {
          const response = await chatApi.getThreadline(id)
          const updated = response.data.data || response.data
          const updatedId = updated?.uuid || updated?.id
          if (!updatedId) return
          results.value = results.value.map((item) =>
            String(item.uuid || item.id) === String(updatedId)
              ? { ...item, ...updated }
              : item
          )
        } catch {
          // One stale row must not stop the others from refreshing.
        }
      })
    )
  } finally {
    syncPolling()
  }
}

const viewResult = (chat) => {
  router.push(`/chats/${chat.uuid || chat.id}`)
}

const clearSelection = () => {
  selectedIds.value = []
  mergeNote.value = ''
  selectionMode.value = false
}

const toggleSelectionMode = () => {
  if (selectionMode.value) {
    clearSelection()
    return
  }
  selectionMode.value = true
}

const toggleSelection = (chat) => {
  const uuid = chat?.uuid
  if (!uuid) return

  const index = selectedIds.value.indexOf(uuid)
  if (index >= 0) {
    const next = [...selectedIds.value]
    next.splice(index, 1)
    selectedIds.value = next
    return
  }

  if (selectedIds.value.length >= MAX_MERGE_COUNT) {
    toast.showWarning(
      t('chats.bulkMerge.limitReached', { max: MAX_MERGE_COUNT })
    )
    return
  }

  selectedIds.value = [...selectedIds.value, uuid]
}

const openMergeConfirm = () => {
  if (selectedCount.value < 2) {
    toast.showWarning(t('chats.bulkMerge.needTwo'))
    return
  }
  showMergeConfirm.value = true
}

const confirmMerge = async () => {
  if (selectedCount.value < 2 || mergeLoading.value) return

  mergeLoading.value = true
  try {
    const response = await chatApi.mergeThreadlines(
      selectedIds.value,
      mergeNote.value.trim()
    )
    const data = response.data.data || response.data || {}
    const canonical = data.threadline || data
    clearSelection()
    showMergeConfirm.value = false
    toast.showSuccess(
      t('chats.bulkMerge.success', { count: data.source_count || 0 })
    )
    if (canonical?.uuid) router.push(`/chats/${canonical.uuid}`)
  } catch (error) {
    console.error('Failed to merge threadlines:', error)
    toast.showError(error.response?.data?.message || t('common.error'))
  } finally {
    mergeLoading.value = false
  }
}

const openRetryFor = (chat) => {
  retryTargets.value = [chat]
  showRetryDialog.value = true
}

const handleRetryConfirm = async (options) => {
  const targets = retryTargets.value
    .map((item) => item.uuid || item.id)
    .filter(Boolean)

  showRetryDialog.value = false
  retryTargets.value = []
  if (!targets.length) return

  try {
    await chatApi.batchRetryThreadlines(targets, options)
    await refreshRows(targets)
    toast.showSuccess(t('retry.batchRetrySuccess', { count: targets.length }))
  } catch (error) {
    console.error('Retry failed:', error)
    await refreshRows(targets)
    toast.showError(error.response?.data?.message || t('retry.batchRetryError'))
  }
}

// Typing should not fire a request per keystroke, and any filter change
// starts the list over at page one.
watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    pagination.value.page = 1
    loadData()
  }, 500)
})

watch([statusFilter, rangeFilter], () => {
  pagination.value.page = 1
  loadData()
})

watch(activeThreadlineIds, syncPolling)

// Coming back from the narrow detail screen, or growing past the threshold,
// needs the list the drawer sits beside.
watch([isWide, openId], () => {
  if (!results.value.length && (!openId.value || isWide.value)) {
    loadData()
  }
})

onMounted(async () => {
  isActive = true
  WIDE.addEventListener('change', syncWide)
  document.addEventListener('keydown', handleDrawerKeys)
  if (!userStore.userInfo?.virtual_email) {
    await userStore.checkAuthStatus()
  }
  refreshData()
})

onUnmounted(() => {
  isActive = false
  WIDE.removeEventListener('change', syncWide)
  document.removeEventListener('keydown', handleDrawerKeys)
  stopPolling()
  if (searchTimer) clearTimeout(searchTimer)
})
</script>
