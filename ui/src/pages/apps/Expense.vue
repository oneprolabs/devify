<template>
  <AppLayout :padded="false">
    <PageHeader
      :parent="{ to: '/apps', label: t('apps.centerTitle') }"
      :title="t('expense.pageTitle')"
      :count="headerSummary"
    >
      <ExpenseTabs
        v-model="activeTab"
        :tabs="tabs"
        class="ml-auto hidden md:flex"
      />
    </PageHeader>

    <!-- Under the header and full width on a phone, where the title row
         cannot hold them. -->
    <div class="flex-none border-b border-line px-4 py-3 md:hidden">
      <ExpenseTabs v-model="activeTab" :tabs="tabs" full />
    </div>

    <div class="flex min-h-0 flex-1" :class="scrollClass">
      <!-- min-w-0: without it this flex child keeps min-width:auto and
           is pushed wider than the viewport by the widest row inside. -->
      <div class="flex min-h-0 min-w-0 flex-1 flex-col" :class="bodyClass">
        <SkeletonRows v-if="loading" :count="5" />

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
            <InvoiceSection
              ref="invoiceSection"
              :cost-per-email="config?.cost_credits_per_email ?? 1"
              @rescanned="refreshData"
              @grouped="groupSection?.load()"
            >
              <!-- Both of these belong to the list, not to the page: they
                   scroll with it and leave the detail panel its full
                   height. -->
              <template #before>
                <div
                  v-if="trips.length || !config?.home_city"
                  class="px-4 pt-3.5 md:px-5"
                >
                  <TripSuggestionCard
                    :trips="trips"
                    :accepting="acceptingTrip"
                    :home-city="config?.home_city || ''"
                    @accept="acceptTrip"
                    @dismiss="dismissTrip"
                    @configure="activeTab = 'settings'"
                  />
                </div>
              </template>

              <template #after>
                <div v-if="links.length" class="px-4 pb-4 md:px-5">
                  <PendingLinkList
                    :links="links"
                    :releasing="releasing"
                    @release="releaseLink"
                  />
                </div>
              </template>
            </InvoiceSection>
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
import ExpenseTabs from '@/components/expense/ExpenseTabs.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import ExpenseEnableCard from '@/components/expense/ExpenseEnableCard.vue'
import ExpensePreferences from '@/components/expense/ExpensePreferences.vue'
import GroupSection from '@/components/expense/GroupSection.vue'
import InvoiceSection from '@/components/expense/InvoiceSection.vue'
import PendingLinkList from '@/components/expense/PendingLinkList.vue'
import ScanPreviewDialog from '@/components/expense/ScanPreviewDialog.vue'
import ScanRunList from '@/components/expense/ScanRunList.vue'
import TripSuggestionCard from '@/components/expense/TripSuggestionCard.vue'
import SkeletonRows from '@/components/ui/SkeletonRows.vue'
import { expenseApi } from '@/api/expense'
import { formatAmount } from '@/utils/formatting'

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
// The invoice tab runs edge to edge, like the canvas; the other two keep
// the padded card layout they are drawn with.
const bodyClass = computed(() =>
  activeTab.value === 'settings' ? 'gap-3.5 p-4 md:p-5' : ''
)

// Invoices and groups put a full-height panel beside a scrolling column,
// so the scrolling happens inside them rather than around them.
const scrollClass = computed(() =>
  activeTab.value === 'settings' ? 'overflow-y-auto' : 'overflow-hidden'
)

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

async function onConfigUpdated(updated) {
  const homeCityChanged = config.value?.home_city !== updated?.home_city
  config.value = updated
  // Setting a home city is what makes trip detection possible at all, so the
  // suggestions have to be fetched again here. Without this the prompt card
  // hides (home city is set now) while trips is still the empty array from
  // the load before it, and the invoices tab shows neither.
  if (homeCityChanged) {
    await loadTrips()
  }
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
