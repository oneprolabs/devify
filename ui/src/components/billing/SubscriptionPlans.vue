<template>
  <div class="flex flex-col">
    <!-- A column of plans, current one highlighted, each saying what it
         gives before what it costs to move there. -->
    <div
      class="flex flex-col overflow-hidden rounded-[11px] border border-line bg-panel"
    >
      <div
        class="flex h-[42px] flex-shrink-0 items-center border-b border-line-soft px-[18px]"
      >
        <span class="text-[13px] font-semibold text-ink">
          {{ t('billing.plans.title') }}
        </span>
      </div>

      <div
        v-for="plan in plans"
        :key="plan.id"
        class="flex flex-col gap-[9px] border-b border-line-soft px-[18px] py-3.5 last:border-b-0"
        :class="isCurrentPlan(plan) ? 'bg-accent-soft' : ''"
      >
        <div class="flex items-baseline gap-[9px]">
          <span
            class="font-display text-sm font-semibold"
            :class="isCurrentPlan(plan) ? 'text-accent' : 'text-ink'"
          >
            {{ plan.name }}
          </span>
          <span
            v-if="isCurrentPlan(plan)"
            class="rounded-sm border border-accent px-1.5 py-px font-mono text-[10px] text-accent"
          >
            {{ t('billing.plans.current') }}
          </span>
          <span
            class="ml-auto font-mono text-xs"
            :class="isCurrentPlan(plan) ? 'text-accent' : 'text-ink-3'"
          >
            {{ plan.monthly_price }}
            <span :class="isCurrentPlan(plan) ? 'opacity-70' : 'text-ink-4'">
              {{ t('billing.plans.perMonth') }}
            </span>
          </span>
        </div>

        <div
          v-if="plan.metadata"
          class="flex flex-wrap gap-x-3.5 gap-y-[5px] font-mono text-[10.5px]"
          :class="isCurrentPlan(plan) ? 'text-accent opacity-80' : 'text-ink-3'"
        >
          <span>
            {{ plan.metadata.max_emails_per_period || plan.credits_per_period }}
            {{ t('billing.plans.creditsPerPeriod') }}
          </span>
          <span>{{ formatPlanStorage(plan.metadata.storage_quota_mb) }}</span>
          <span>{{ formatPlanRetention(plan.metadata.retention_days) }}</span>
        </div>

        <div v-if="!isCurrentPlan(plan)">
          <button
            v-if="!rechargeEnabled"
            disabled
            class="flex h-8 w-full items-center justify-center rounded border border-line text-[12.5px] text-ink-4"
          >
            {{ t('billing.plans.rechargeUnavailable') }}
          </button>
          <button
            v-else-if="canUpgrade(plan)"
            type="button"
            class="font-display flex h-8 w-full items-center justify-center rounded bg-accent text-[12.5px] font-medium text-accent-on transition-opacity hover:opacity-90 disabled:opacity-50"
            :disabled="upgrading"
            @click="handleUpgrade(plan)"
          >
            {{ t('billing.plans.upgradeTo', { plan: plan.name }) }}
          </button>
          <button
            v-else-if="canDowngrade(plan)"
            type="button"
            class="font-display flex h-8 w-full items-center justify-center rounded border border-line text-[12.5px] text-ink-2 transition-colors hover:border-ink-4"
            @click="handleDowngradeClick(plan)"
          >
            {{ t('billing.plans.downgradeTo', { plan: plan.name }) }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="showCancelDialog"
      class="fixed inset-0 bg-ink-2 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-start justify-center pt-20"
      @click.self="showCancelDialog = false"
    >
      <div
        class="relative mx-auto p-6 border max-w-md w-full shadow-lg rounded-lg bg-panel"
      >
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-ink">
            {{ t('billing.cancel.title') }}
          </h3>
          <button
            @click="showCancelDialog = false"
            class="text-ink-4 hover:text-ink-2"
          >
            <svg
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div class="mb-6">
          <p class="text-sm text-ink-2 mb-4">
            {{ t('billing.cancel.confirmMessage') }}
          </p>
          <div class="bg-warn-soft rounded-lg p-4 border border-warn">
            <div class="flex gap-3">
              <div class="flex-shrink-0">
                <svg
                  class="h-5 w-5 text-warn"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <div class="flex-1 space-y-2">
                <p class="text-sm text-warn">
                  {{ t('billing.cancel.effectiveNote') }}
                </p>
                <p
                  v-if="formattedPeriodEnd"
                  class="text-sm font-medium text-warn"
                >
                  {{
                    t('billing.cancel.availableUntil', {
                      date: formattedPeriodEnd
                    })
                  }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3">
          <button
            type="button"
            @click="showCancelDialog = false"
            class="px-4 py-2 text-sm font-medium text-ink-2 bg-chip hover:bg-chip rounded-md"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="confirmCancelSubscription"
            :disabled="canceling"
            class="px-4 py-2 text-sm font-medium text-accent-on bg-bad hover:bg-bad rounded-md disabled:opacity-50"
          >
            {{ canceling ? t('common.loading') : t('billing.cancel.confirm') }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="showDowngradeDialog"
      class="fixed inset-0 bg-ink-2 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-start justify-center pt-20"
      @click.self="showDowngradeDialog = false"
    >
      <div
        class="relative mx-auto p-6 border max-w-md w-full shadow-lg rounded-lg bg-panel"
      >
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-ink">
            {{ t('billing.downgrade.title') }}
          </h3>
          <button
            @click="showDowngradeDialog = false"
            class="text-ink-4 hover:text-ink-2"
          >
            <svg
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div class="mb-6">
          <p class="text-sm text-ink-2 mb-4">
            {{
              t('billing.downgrade.confirmMessage', {
                plan: selectedDowngradePlan?.name || ''
              })
            }}
          </p>
          <div class="bg-accent-soft rounded-lg p-4 border border-accent">
            <div class="flex gap-3">
              <div class="flex-shrink-0">
                <svg
                  class="h-5 w-5 text-accent"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <div class="flex-1 space-y-2">
                <p class="text-sm text-accent">
                  {{ t('billing.downgrade.effectiveNote') }}
                </p>
                <p
                  v-if="formattedPeriodEnd"
                  class="text-sm font-medium text-accent"
                >
                  {{
                    t('billing.downgrade.availableUntil', {
                      date: formattedPeriodEnd
                    })
                  }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3">
          <button
            type="button"
            @click="showDowngradeDialog = false"
            class="px-4 py-2 text-sm font-medium text-ink-2 bg-chip hover:bg-chip rounded-md"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="confirmDowngrade"
            :disabled="downgrading"
            class="px-4 py-2 text-sm font-medium text-accent-on bg-warn hover:bg-warn rounded-md disabled:opacity-50"
          >
            {{
              downgrading ? t('common.loading') : t('billing.downgrade.confirm')
            }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="showResumeDialog"
      class="fixed inset-0 bg-ink-2 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-start justify-center pt-20"
      @click.self="showResumeDialog = false"
    >
      <div
        class="relative mx-auto p-6 border max-w-md w-full shadow-lg rounded-lg bg-panel"
      >
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-ink">
            {{ t('billing.resume.title') }}
          </h3>
          <button
            @click="showResumeDialog = false"
            class="text-ink-4 hover:text-ink-2"
          >
            <svg
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div class="mb-6">
          <p class="text-sm text-ink-2 mb-4">
            {{ t('billing.resume.confirmMessage') }}
          </p>
          <div class="bg-ok-soft rounded-lg p-4 border border-ok">
            <div class="flex gap-3">
              <div class="flex-shrink-0">
                <svg
                  class="h-5 w-5 text-ok"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <div class="flex-1 space-y-2">
                <p class="text-sm text-ok">
                  {{ t('billing.resume.effectiveNote') }}
                </p>
                <p
                  v-if="formattedPeriodEnd"
                  class="text-sm font-medium text-ok"
                >
                  {{
                    t('billing.resume.nextBillingDate', {
                      date: formattedPeriodEnd
                    })
                  }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3">
          <button
            type="button"
            @click="showResumeDialog = false"
            class="px-4 py-2 text-sm font-medium text-ink-2 bg-chip hover:bg-chip rounded-md"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="confirmResumeSubscription"
            :disabled="resuming"
            class="px-4 py-2 text-sm font-medium text-accent-on bg-ok hover:bg-ok rounded-md disabled:opacity-50"
          >
            {{ resuming ? t('common.loading') : t('billing.resume.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Updated with date display in dialogs
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { format } from 'date-fns'
import { zhCN, enUS } from 'date-fns/locale'
import billingApi from '@/api/billing'

defineExpose({
  openCancelDialog: () => handleManageSubscription(),
  openResumeDialog: () => handleResumeClick(),
  canCancel: () => rechargeEnabled.value && !isInternalUser.value,
  canResume: () => isCanceledButActive.value
})

const { t, locale } = useI18n()
const toast = useToast()

const props = defineProps({
  currentSubscription: {
    type: Object,
    default: null
  },
  billingStatus: {
    type: Object,
    default: null
  }
})

const emit = defineEmits([
  'subscription-updated',
  'operation-success',
  'operation-error'
])

const plans = ref([])
const upgrading = ref(false)
const showCancelDialog = ref(false)
const canceling = ref(false)
const showDowngradeDialog = ref(false)
const downgrading = ref(false)
const selectedDowngradePlan = ref(null)
const showResumeDialog = ref(false)
const resuming = ref(false)

const currentPlanSlug = computed(() => {
  return props.currentSubscription?.plan_slug || 'free'
})

const isInternalUser = computed(() => {
  return (
    props.currentSubscription?.plan_slug === 'internal' ||
    props.currentSubscription?.plan_is_internal ||
    props.currentSubscription?.plan?.is_internal
  )
})

const hasBillingStatus = computed(() => props.billingStatus != null)

const rechargeEnabled = computed(() => {
  if (!hasBillingStatus.value) return true
  if (
    Object.prototype.hasOwnProperty.call(
      props.billingStatus,
      'recharge_enabled'
    )
  ) {
    return props.billingStatus.recharge_enabled === true
  }
  return props.billingStatus.stripe_configured === true
})

function canSelfPurchasePlan(plan) {
  if (!hasBillingStatus.value) {
    return true
  }
  if (!rechargeEnabled.value) {
    return false
  }
  if (!plan || plan.is_internal) {
    return false
  }
  if (plan.status && plan.status !== 'active') {
    return false
  }
  return plan.allow_self_purchase === true
}

const formattedPeriodEnd = computed(() => {
  if (!props.currentSubscription?.current_period_end) return ''

  const date = new Date(props.currentSubscription.current_period_end)
  const dateLocale = locale.value === 'zh-CN' ? zhCN : enUS

  if (locale.value === 'zh-CN') {
    return format(date, 'yyyy年M月d日', { locale: dateLocale })
  } else {
    return format(date, 'MMM dd, yyyy', { locale: dateLocale })
  }
})

const planOrder = { free: 0, starter: 1, standard: 2, pro: 3 }

const isCanceledButActive = computed(() => {
  return (
    props.currentSubscription &&
    props.currentSubscription.status === 'active' &&
    props.currentSubscription.auto_renew === false
  )
})

function isCurrentPlan(plan) {
  return plan.slug === currentPlanSlug.value
}

function canUpgrade(plan) {
  if (!canSelfPurchasePlan(plan)) {
    return false
  }
  if (isInternalUser.value) {
    return false
  }
  const currentOrder = planOrder[currentPlanSlug.value] || 0
  const targetOrder = planOrder[plan.slug] || 0
  return targetOrder > currentOrder
}

function canDowngrade(plan) {
  if (!canSelfPurchasePlan(plan)) {
    return false
  }
  if (isInternalUser.value) {
    return false
  }
  if (isCanceledButActive.value) {
    return false
  }
  const currentOrder = planOrder[currentPlanSlug.value] || 0
  const targetOrder = planOrder[plan.slug] || 0
  return targetOrder < currentOrder && plan.slug !== 'free'
}

function formatPlanStorage(storageMb) {
  if (!storageMb) return '-'
  if (storageMb >= 1024) {
    return `${(storageMb / 1024).toFixed(0)} GB`
  }
  return `${storageMb} MB`
}

function formatPlanRetention(retentionDays) {
  if (retentionDays === null || retentionDays === undefined) {
    return t('billing.creditsInfo.retentionNotSet')
  }
  if (retentionDays === -1) {
    return t('billing.creditsInfo.retentionPermanent')
  }
  if (retentionDays >= 365) {
    const years = Math.floor(retentionDays / 365)
    if (years === 1) {
      return locale.value === 'zh-CN' ? '1年' : '1 year'
    }
    return t('billing.creditsInfo.retentionYears', { years })
  }
  return t('billing.creditsInfo.retentionDays', { days: retentionDays })
}

async function fetchPlans() {
  try {
    const response = await billingApi.getPlans()
    const plansData = response.data.data || response.data
    plans.value = plansData
  } catch (error) {
    console.error('Failed to fetch plans:', error)
  }
}

async function handleUpgrade(plan) {
  if (isInternalUser.value) {
    return
  }
  if (!plan.stripe_price_id) {
    toast.showWarning(t('billing.plans.rechargeUnavailable'))
    return
  }

  upgrading.value = true

  try {
    const response = await billingApi.createCheckoutSession(
      plan.stripe_price_id
    )
    const responseData = response.data.data || response.data

    if (responseData.checkout_url) {
      upgrading.value = false
      window.location.href = responseData.checkout_url
      return
    }

    console.error('No checkout URL in response:', responseData)
    upgrading.value = false
    emit('operation-error', t('billing.plans.upgradeFailed'))
  } catch (error) {
    console.error('Failed to create checkout session:', error)
    upgrading.value = false
    emit('operation-error', t('billing.plans.upgradeFailed'))
  }
}

function handleManageSubscription() {
  if (isInternalUser.value) {
    return
  }
  showCancelDialog.value = true
}

function handleDowngradeClick(plan) {
  if (isInternalUser.value) {
    return
  }
  selectedDowngradePlan.value = plan
  showDowngradeDialog.value = true
}

async function confirmDowngrade() {
  if (isInternalUser.value) {
    return
  }
  if (!selectedDowngradePlan.value) return

  downgrading.value = true
  try {
    await billingApi.scheduleDowngrade(
      selectedDowngradePlan.value.stripe_price_id
    )
    showDowngradeDialog.value = false
    emit('operation-success', 'downgrade')
    emit('subscription-updated')
  } catch (error) {
    console.error('Failed to schedule downgrade:', error)
    showDowngradeDialog.value = false
    emit('operation-error', t('billing.downgrade.failed'))
  } finally {
    downgrading.value = false
  }
}

async function confirmCancelSubscription() {
  if (isInternalUser.value) {
    return
  }
  if (!props.currentSubscription) {
    return
  }

  canceling.value = true

  try {
    await billingApi.cancelSubscription(props.currentSubscription.id)
    showCancelDialog.value = false
    emit('operation-success', 'cancel')
    emit('subscription-updated')
  } catch (error) {
    console.error('Failed to cancel subscription:', error)
    showCancelDialog.value = false
    emit('operation-error', t('billing.plans.cancelFailed'))
  } finally {
    canceling.value = false
  }
}

function handleResumeClick() {
  if (isInternalUser.value) {
    return
  }
  showResumeDialog.value = true
}

async function confirmResumeSubscription() {
  if (isInternalUser.value) {
    return
  }
  if (!props.currentSubscription) {
    return
  }

  resuming.value = true

  try {
    await billingApi.resumeSubscription(props.currentSubscription.id)
    showResumeDialog.value = false
    emit('operation-success', 'resume')
    emit('subscription-updated')
  } catch (error) {
    console.error('Failed to resume subscription:', error)
    showResumeDialog.value = false
    emit('operation-error', t('billing.plans.resumeFailed'))
  } finally {
    resuming.value = false
  }
}

onMounted(() => {
  fetchPlans()
})
</script>
