<template>
  <AppLayout :padded="false">
    <PageHeader
      :parent="{ to: '/apps', label: t('apps.centerTitle') }"
      :title="t('expense.pageTitle')"
      :count="headerSummary"
    >
      <!-- Three resources, not three states: an invoice's status is a filter
           inside the first one. -->
      <div
        class="ml-auto flex h-8 items-center overflow-hidden rounded-md border border-line"
        role="tablist"
      >
        <button
          v-for="(tab, index) in tabs"
          :key="tab.value"
          type="button"
          role="tab"
          class="font-display flex h-8 items-center px-3.5 text-[12.5px] transition-colors"
          :aria-selected="activeTab === tab.value"
          :class="[
            activeTab === tab.value
              ? 'bg-accent-soft font-medium text-accent'
              : 'text-ink-2 hover:bg-chip',
            index ? 'border-l border-line' : ''
          ]"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
    </PageHeader>

    <div class="min-h-0 flex-1 overflow-y-auto p-4 md:p-5">
      <div class="flex flex-col gap-3.5">
        <BaseCard v-if="loading">
          <div class="space-y-4 animate-pulse">
            <div class="h-5 w-40 rounded bg-chip"></div>
            <div class="h-20 rounded bg-chip"></div>
          </div>
        </BaseCard>

        <template v-else>
          <p
            v-if="error"
            class="rounded-lg border border-bad bg-bad-soft p-4 text-sm text-bad"
          >
            {{ error }}
          </p>

          <BaseCard v-if="activeTab !== 'settings' && !config?.enabled">
            <p class="py-8 text-center text-sm text-ink-3">
              {{ t('expense.disabledHint') }}
            </p>
          </BaseCard>

          <!-- Invoices: everything the app found, filtered by where each
               one is headed rather than split across another row of tabs -->
          <template v-else-if="activeTab === 'invoices'">
            <TripSuggestionCard
              :trips="trips"
              :accepting="acceptingTrip"
              @accept="acceptTrip"
              @dismiss="dismissTrip"
            />

            <InvoiceSection
              ref="invoiceSection"
              @rescanned="refreshData"
              @grouped="groupSection?.load()"
            />

            <PendingLinkList
              :links="links"
              :releasing="releasing"
              @release="releaseLink"
            />
          </template>

          <!-- Groups: one group is one real claim form -->
          <template v-else-if="activeTab === 'groups'">
            <GroupSection ref="groupSection" />
          </template>

          <!-- Settings: the switch, how scanning behaves, and its history -->
          <template v-else>
            <ExpenseEnableCard
              v-if="config"
              :model-value="config"
              :saving="saving"
              @toggle="handleToggle"
            />

            <ExpensePreferences
              v-if="config?.enabled"
              :config="config"
              @updated="onConfigUpdated"
            />

            <ScanRunList
              v-if="config?.enabled"
              :runs="runs"
              :scanning="scanning"
              @scan="openPreview"
            />
          </template>
        </template>
      </div>
    </div>

    <ScanPreviewDialog
      v-if="previewOpen"
      :preview="preview"
      :loading="previewLoading"
      :error="previewError"
      @close="previewOpen = false"
      @confirm="confirmScan"
    />
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import ExpenseEnableCard from '@/components/expense/ExpenseEnableCard.vue'
import ExpensePreferences from '@/components/expense/ExpensePreferences.vue'
import GroupSection from '@/components/expense/GroupSection.vue'
import InvoiceSection from '@/components/expense/InvoiceSection.vue'
import PendingLinkList from '@/components/expense/PendingLinkList.vue'
import ScanPreviewDialog from '@/components/expense/ScanPreviewDialog.vue'
import ScanRunList from '@/components/expense/ScanRunList.vue'
import TripSuggestionCard from '@/components/expense/TripSuggestionCard.vue'
import { expenseApi } from '@/api/expense'

const { t } = useI18n()

// The header says what is still waiting to be claimed, which is the number
// this app exists to bring down.
const stats = ref(null)
const headerSummary = computed(() => {
  if (!stats.value) return null
  return t('expense.headerSummary', {
    count: stats.value.unfiled ?? 0,
    amount: formatAmount(stats.value.amount ?? 0)
  })
})

function formatAmount(amount) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount)
}

async function loadStats() {
  try {
    stats.value = await expenseApi.getStats()
  } catch (error) {
    console.error('Failed to load expense stats:', error)
  }
}

// Tabs separate resources, not states: an invoice's status is a filter
// within its own list, so it never becomes a second row of tabs.
const activeTab = ref('invoices')
const tabs = computed(() => [
  { value: 'invoices', label: t('expense.tabsInvoices') },
  { value: 'groups', label: t('expense.tabsGroups') },
  { value: 'settings', label: t('expense.tabsSettings') }
])

const config = ref(null)
const runs = ref([])
const links = ref([])
const trips = ref([])
const loading = ref(true)
const saving = ref(false)
const scanning = ref(false)
const releasing = ref('')
const acceptingTrip = ref('')
const error = ref('')

const invoiceSection = ref(null)
const groupSection = ref(null)

const previewOpen = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const preview = ref(null)

// A link belongs on this list only when allowing it once would actually
// produce the invoice. A page that wants a login, a file that was too
// large or the wrong type cannot be fixed from here, and listing them as
// pending work left the user with a to-do list of nothing to do.
const ACTIONABLE_LINK_STATES = ['blocked_domain', 'not_https']

function isActionable(link) {
  return (
    ACTIONABLE_LINK_STATES.includes(link.fetch_status) && !link.user_allowed
  )
}

function readError(err, fallbackKey) {
  return err?.response?.data?.message || t(fallbackKey)
}

async function loadRuns() {
  if (!config.value?.enabled) {
    runs.value = []
    links.value = []
    return
  }
  try {
    const [runList, linkList] = await Promise.all([
      expenseApi.getScanRuns(),
      expenseApi.getLinks()
    ])
    runs.value = runList
    links.value = linkList.filter(isActionable)
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

// Trip detection is pure rule work on data already extracted, so it is
// refreshed on load rather than hidden behind a button.
async function loadTrips() {
  if (!config.value?.enabled) {
    trips.value = []
    return
  }
  try {
    const result = await expenseApi.refreshTrips()
    trips.value = result.suggestions || []
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

async function refreshData() {
  await Promise.all([loadRuns(), loadTrips()])
  await invoiceSection.value?.load()
  await groupSection.value?.load()
}

async function loadConfig() {
  loading.value = true
  error.value = ''
  try {
    config.value = await expenseApi.getConfig()
    await Promise.all([loadRuns(), loadTrips()])
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  } finally {
    loading.value = false
  }
}

function onConfigUpdated(updated) {
  config.value = updated
}

async function handleToggle(enabled) {
  saving.value = true
  error.value = ''
  try {
    config.value = await expenseApi.updateConfig({ enabled })
    await Promise.all([loadRuns(), loadTrips()])
  } catch (err) {
    error.value = readError(err, 'expense.saveFailed')
  } finally {
    saving.value = false
  }
}

// The cost is always shown before a scan starts, never after.
async function openPreview() {
  previewOpen.value = true
  previewLoading.value = true
  previewError.value = ''
  preview.value = null
  try {
    preview.value = await expenseApi.previewScan({})
  } catch (err) {
    previewError.value = readError(err, 'expense.scan.previewFailed')
  } finally {
    previewLoading.value = false
  }
}

async function confirmScan() {
  scanning.value = true
  previewOpen.value = false
  error.value = ''
  try {
    await expenseApi.startScan({})
    await refreshData()
  } catch (err) {
    error.value = readError(err, 'expense.scan.startFailed')
  } finally {
    scanning.value = false
  }
}

async function acceptTrip(trip) {
  acceptingTrip.value = trip.uuid
  error.value = ''
  try {
    await expenseApi.acceptTrip(trip.uuid)
    await refreshData()
  } catch (err) {
    error.value = readError(err, 'expense.trips.acceptFailed')
  } finally {
    acceptingTrip.value = ''
  }
}

async function dismissTrip(trip) {
  try {
    await expenseApi.dismissTrip(trip.uuid)
    await loadTrips()
  } catch (err) {
    error.value = readError(err, 'expense.trips.acceptFailed')
  }
}

async function releaseLink(link) {
  releasing.value = link.uuid
  error.value = ''
  try {
    await expenseApi.releaseLink(link.uuid)
    await loadRuns()
  } catch (err) {
    error.value = readError(err, 'expense.links.releaseFailed')
  } finally {
    releasing.value = ''
  }
}

onMounted(() => {
  loadConfig()
  loadStats()
})
</script>
