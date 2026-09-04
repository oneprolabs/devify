<template>
  <!-- One bar: which plan, the period it runs for, and how much of its
       credits is left — the three things a subscription page is asked. -->
  <div
    v-if="credits || subscription"
    class="flex flex-col gap-4 rounded-[11px] border border-line bg-panel px-5 py-[18px] xl:flex-row xl:items-center xl:gap-0"
  >
    <div
      class="flex flex-col gap-[7px] xl:flex-none xl:border-r xl:border-line-soft xl:pr-7"
    >
      <div class="flex items-center gap-[9px]">
        <span class="font-display text-[19px] font-semibold text-ink">
          {{ planName }}
        </span>
        <span
          v-if="subscription?.status"
          class="rounded-sm px-[7px] py-0.5 font-mono text-[10.5px]"
          :class="getStatusIconClass(subscription.status)"
        >
          {{ getStatusText(subscription.status) }}
        </span>
      </div>
      <span v-if="providerLine" class="font-mono text-[11px] text-ink-4">
        {{ providerLine }}
      </span>
    </div>

    <div
      class="flex flex-col gap-[5px] xl:flex-none xl:border-r xl:border-line-soft xl:px-7"
    >
      <span class="text-[11px] text-ink-3">
        {{ t('billing.currentSubscription.currentPeriod') }}
      </span>
      <span class="font-mono text-[12.5px] text-ink">
        {{ formatDate(periodStart) }} → {{ formatDate(periodEnd) }}
      </span>
    </div>

    <div
      v-if="daysRemaining !== null"
      class="flex flex-col gap-[5px] xl:flex-none xl:border-r xl:border-line-soft xl:px-7"
    >
      <span class="text-[11px] text-ink-3">
        {{ t('billing.currentSubscription.daysRemaining') }}
      </span>
      <span class="font-mono text-[12.5px] text-ink">
        {{ t('billing.currentSubscription.days', { days: daysRemaining }) }}
      </span>
    </div>

    <div class="flex min-w-0 flex-1 flex-col gap-2 xl:px-7">
      <div class="flex items-baseline justify-between gap-3">
        <span class="text-[11px] text-ink-3">
          {{ t('billing.currentSubscription.creditsUsage') }}
        </span>
        <span class="font-mono text-[12.5px] text-ink-3">
          {{
            t('billing.currentSubscription.creditsSplit', { used: usedCredits })
          }}
          <span class="font-medium text-ink">{{
            credits?.available_credits ?? 0
          }}</span>
          / {{ credits?.total_credits ?? 0 }}
        </span>
      </div>
      <div class="h-1.5 rounded-md bg-chip">
        <div
          class="h-1.5 rounded-md bg-accent transition-all"
          :style="{ width: `${usedPercentage}%` }"
        ></div>
      </div>
    </div>

    <div class="flex flex-shrink-0 items-center gap-[9px] xl:pl-2">
      <slot name="actions" />
    </div>
  </div>

  <div
    v-else
    class="rounded-[11px] border border-line bg-panel px-5 py-8 text-center text-sm text-ink-3"
  >
    {{ t('common.loading') }}
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, differenceInDays } from 'date-fns'
import { usePreferencesStore } from '@/store/preferences'

const { t } = useI18n()
const preferencesStore = usePreferencesStore()

const props = defineProps({
  subscription: {
    type: Object,
    default: null
  },
  credits: {
    type: Object,
    default: null
  }
})

function getStatusIconClass(status) {
  const classes = {
    active: 'bg-ok-soft text-ok',
    canceled: 'bg-chip text-ink-2',
    trialing: 'bg-accent-soft text-accent',
    past_due: 'bg-bad-soft text-bad'
  }
  return classes[status] || 'bg-chip text-ink-2'
}

function getStatusText(status) {
  const texts = {
    active: t('billing.status.active'),
    canceled: t('billing.status.canceled'),
    trialing: t('billing.status.trialing'),
    past_due: t('billing.status.pastDue')
  }
  return texts[status] || status
}

function formatDate(dateString) {
  if (!dateString) return '-'
  const date = new Date(dateString)

  const isZhCN = preferencesStore.currentLanguage === 'zh-CN'

  if (isZhCN) {
    return format(date, 'yyyy年M月d日')
  } else {
    return format(date, 'MMM dd, yyyy')
  }
}

// A free account has no subscription record but still has a credit period,
// which is the window this bar is really describing.
const periodStart = computed(
  () =>
    props.subscription?.current_period_start ||
    props.credits?.period_start ||
    null
)
const periodEnd = computed(
  () =>
    props.subscription?.current_period_end || props.credits?.period_end || null
)

const planName = computed(
  () =>
    props.subscription?.plan_name ||
    props.credits?.plan_name ||
    t('billing.plans.freePlan')
)

const daysRemaining = computed(() => {
  if (!periodEnd.value) {
    return null
  }

  const endDate = new Date(periodEnd.value)
  const today = new Date()
  const days = differenceInDays(endDate, today)

  return days > 0 ? days : 0
})

const usedCredits = computed(() => {
  const total = props.credits?.total_credits ?? 0
  const available = props.credits?.available_credits ?? 0
  return Math.max(0, total - available)
})

// The bar fills with what has been spent, which is the number that grows.
const usedPercentage = computed(() => {
  const total = props.credits?.total_credits
  if (!total) return 0
  return Math.round((usedCredits.value / total) * 100)
})

const providerLine = computed(() => {
  const provider = props.subscription?.provider
  if (!provider) return ''
  const renews = props.subscription?.cancel_at_period_end
    ? t('billing.currentSubscription.autoRenewOff')
    : t('billing.currentSubscription.autoRenewOn')
  return `${provider} · ${renews}`
})
</script>
