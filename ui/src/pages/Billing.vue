<template>
  <AppLayout :padded="false">
    <PageHeader
      :title="t('billing.title')"
      :parent="{ to: '/settings', label: t('common.settings') }"
      parent-mobile-only
      gutter="md"
    >
      <span class="hidden text-xs text-ink-3 lg:block">
        {{ t('billing.description') }}
      </span>
    </PageHeader>

    <div class="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
      <div class="flex flex-col gap-4">
        <p
          v-if="successMessage"
          class="rounded-lg border border-ok bg-ok-soft px-4 py-2.5 text-sm text-ok"
        >
          {{ successMessage }}
        </p>
        <p
          v-if="errorMessage"
          class="rounded-lg border border-bad bg-bad-soft px-4 py-2.5 text-sm text-bad"
        >
          {{ errorMessage }}
        </p>
        <div
          v-if="billingStatus && billingStatus.recharge_enabled === false"
          class="rounded-lg border border-warn bg-warn-soft p-4 text-sm text-warn"
        >
          <p class="font-medium">
            {{ t('billing.plans.stripeNotConfigured') }}
          </p>
          <p class="mt-1">{{ t('billing.status.stripeMissingHint') }}</p>
        </div>

        <!-- The page's own shape while it waits: the plan bar, then the
             two columns under it. A spinner would say less. -->
        <div v-if="loading" class="flex flex-col gap-4" aria-busy="true">
          <div
            class="flex flex-col gap-3.5 rounded-[11px] border border-line bg-panel px-5 py-[18px] md:flex-row md:items-center md:gap-7"
          >
            <span class="h-[13px] w-[72px] flex-none rounded-[5px] bg-chip"></span>
            <span class="flex flex-col gap-[7px]">
              <span class="h-2 w-14 rounded-sm bg-line-soft"></span>
              <span class="h-2.5 w-[168px] rounded-[5px] bg-chip"></span>
            </span>
            <span class="flex flex-col gap-[7px]">
              <span class="h-2 w-12 rounded-sm bg-line-soft"></span>
              <span class="h-2.5 w-14 rounded-[5px] bg-chip"></span>
            </span>
            <span class="flex min-w-0 flex-1 flex-col gap-[7px] opacity-55">
              <span class="h-2 w-20 rounded-sm bg-line-soft"></span>
              <span class="h-1.5 w-full rounded-sm bg-chip"></span>
            </span>
          </div>

          <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_384px]">
            <div
              class="flex flex-col gap-3.5 rounded-[11px] border border-line bg-panel px-5 py-4"
            >
              <span class="h-2.5 w-28 rounded-[5px] bg-chip"></span>
              <div class="flex h-[180px] items-end gap-[7px] pb-5">
                <span
                  v-for="(height, index) in CHART_BARS"
                  :key="index"
                  class="min-w-0 flex-1 rounded-sm bg-chip"
                  :style="{ height }"
                ></span>
              </div>
            </div>

            <div
              class="flex flex-col gap-3.5 rounded-[11px] border border-line bg-panel px-5 py-4"
            >
              <span class="h-2.5 w-20 rounded-[5px] bg-chip"></span>
              <div
                v-for="(row, index) in PLAN_ROWS"
                :key="index"
                class="flex flex-col gap-[7px]"
                :style="{ opacity: index === PLAN_ROWS.length - 1 ? 0.55 : 1 }"
              >
                <span
                  class="h-2.5 rounded-[5px] bg-chip"
                  :style="{ width: row[0] }"
                ></span>
                <span
                  class="h-2 rounded-sm bg-line-soft"
                  :style="{ width: row[1] }"
                ></span>
              </div>
            </div>
          </div>
        </div>

        <template v-else>
          <CurrentSubscription
            :subscription="currentSubscription"
            :credits="credits"
          >
            <template #actions>
              <button
                v-if="plansRef?.canResume?.()"
                type="button"
                class="font-display flex h-[34px] items-center rounded border border-line px-3.5 text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:border-ink-4"
                @click="plansRef.openResumeDialog()"
              >
                {{ t('billing.resume.title') }}
              </button>
              <button
                v-else-if="plansRef?.canCancel?.()"
                type="button"
                class="font-display flex h-[34px] items-center rounded border border-line px-3.5 text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:border-ink-4"
                @click="plansRef.openCancelDialog()"
              >
                {{ t('billing.cancel.title') }}
              </button>
            </template>
          </CurrentSubscription>

          <div class="flex flex-col gap-4 xl:flex-row">
            <div class="flex min-w-0 flex-1 flex-col gap-4">
              <UsageChart />
              <CreditUsageList />
            </div>

            <div class="flex flex-col gap-4 xl:w-96 xl:flex-none">
              <SubscriptionPlans
                ref="plansRef"
                :current-subscription="currentSubscription"
                :billing-status="billingStatus"
                @subscription-updated="handleSubscriptionUpdated"
                @operation-success="handleOperationSuccess"
                @operation-error="handleOperationError"
              />
              <CreditsInfoCard
                :subscription="currentSubscription"
                :credits="credits"
              />
            </div>
          </div>
        </template>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import CreditsInfoCard from '@/components/billing/CreditsInfoCard.vue'
import CurrentSubscription from '@/components/billing/CurrentSubscription.vue'
import SubscriptionPlans from '@/components/billing/SubscriptionPlans.vue'
import UsageChart from '@/components/billing/UsageChart.vue'
import CreditUsageList from '@/components/billing/CreditUsageList.vue'
import billingApi from '@/api/billing'

const { t } = useI18n()

// The summary bar's cancel and resume reach the dialogs the plan list owns.
const plansRef = ref(null)
const route = useRoute()
const router = useRouter()

// Fixed proportions so the wait keeps one silhouette.
const CHART_BARS = [
  '38%', '61%', '29%', '74%', '52%', '83%', '44%', '67%',
  '31%', '58%', '77%', '41%', '69%', '35%', '55%'
]
const PLAN_ROWS = [
  ['42%', '68%'],
  ['36%', '61%'],
  ['48%', '72%'],
  ['33%', '57%']
]

const loading = ref(true)
const billingStatus = ref(null)
const currentSubscription = ref(null)
const credits = ref(null)
const successMessage = ref('')
const errorMessage = ref('')
let billingSyncTimer = null

async function fetchData() {
  loading.value = true

  try {
    const [statusRes, subscriptionRes, creditsRes] = await Promise.allSettled([
      billingApi.getStatus(),
      billingApi.getCurrentSubscription(),
      billingApi.getUserCredits()
    ])

    if (statusRes.status === 'fulfilled') {
      const statusData =
        statusRes.value.data?.data ?? statusRes.value.data ?? null
      billingStatus.value = statusData
    }

    if (subscriptionRes.status === 'fulfilled') {
      const subscriptionData =
        subscriptionRes.value.data?.data ?? subscriptionRes.value.data ?? null
      currentSubscription.value = subscriptionData
    }

    if (creditsRes.status === 'fulfilled') {
      const creditsData = creditsRes.value.data?.data ?? creditsRes.value.data
      credits.value = creditsData
    }
  } catch (error) {
    console.error('Failed to fetch billing data:', error)
    errorMessage.value = t('billing.errors.fetchFailed')
  } finally {
    loading.value = false
  }
}

function handleSubscriptionUpdated() {
  fetchData()
}

function handleOperationSuccess(operationType) {
  if (operationType === 'cancel') {
    successMessage.value = t('billing.messages.cancelSuccess')
  } else if (operationType === 'downgrade') {
    successMessage.value = t('billing.messages.downgradeSuccess')
  } else if (operationType === 'resume') {
    successMessage.value = t('billing.messages.resumeSuccess')
  }

  setTimeout(() => {
    successMessage.value = ''
  }, 5000)
}

function handleOperationError(errorMsg) {
  errorMessage.value = errorMsg

  setTimeout(() => {
    errorMessage.value = ''
  }, 5000)
}

function handleStripeCallback() {
  const success = route.query.success
  const canceled = route.query.canceled

  if (success === 'true') {
    successMessage.value = t('billing.messages.paymentSuccess')

    router.replace({ query: {} })

    let attempts = 0
    const maxAttempts = 5
    const syncIntervalMs = 2000

    const syncBillingState = async () => {
      attempts += 1
      await fetchData()

      if (
        currentSubscription.value?.status === 'active' ||
        attempts >= maxAttempts
      ) {
        billingSyncTimer = null
        return
      }

      billingSyncTimer = window.setTimeout(syncBillingState, syncIntervalMs)
    }

    if (billingSyncTimer) {
      window.clearTimeout(billingSyncTimer)
      billingSyncTimer = null
    }

    billingSyncTimer = window.setTimeout(syncBillingState, syncIntervalMs)
  } else if (canceled === 'true') {
    errorMessage.value = t('billing.messages.paymentCanceled')

    router.replace({ query: {} })
  }
}

onMounted(() => {
  handleStripeCallback()
  fetchData()
})

onUnmounted(() => {
  if (billingSyncTimer) {
    window.clearTimeout(billingSyncTimer)
    billingSyncTimer = null
  }
})
</script>
