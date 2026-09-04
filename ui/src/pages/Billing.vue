<template>
  <AppLayout :padded="false">
    <PageHeader :title="t('billing.title')" gutter="md">
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

        <div
          v-if="loading"
          class="flex items-center justify-center gap-3 py-12"
        >
          <span
            class="h-8 w-8 animate-spin rounded-full border-b-2 border-accent"
          ></span>
          <p class="text-sm text-ink-3">{{ t('common.loading') }}</p>
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
                class="font-display flex h-[34px] items-center rounded border border-line px-3.5 text-[12.5px] text-ink-2 transition-colors hover:border-ink-4"
                @click="plansRef.openResumeDialog()"
              >
                {{ t('billing.resume.title') }}
              </button>
              <button
                v-else-if="plansRef?.canCancel?.()"
                type="button"
                class="font-display flex h-[34px] items-center rounded border border-line px-3.5 text-[12.5px] text-ink-2 transition-colors hover:border-ink-4"
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
