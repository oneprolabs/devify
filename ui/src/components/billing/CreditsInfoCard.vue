<template>
  <div
    class="flex flex-col gap-[11px] rounded-[11px] border border-line bg-panel px-[18px] py-4"
  >
    <span class="text-[13px] font-semibold text-ink">
      {{ t('billing.creditsInfo.title') }}
    </span>
    <p class="text-xs leading-[1.7] text-ink-3">
      {{ t('billing.creditsInfo.description') }}
    </p>

    <div class="flex flex-col gap-[7px] pt-0.5">
      <div v-for="row in rows" :key="row.key" class="flex justify-between">
        <span class="text-xs text-ink-3">{{ row.label }}</span>
        <span class="font-mono text-xs text-ink">{{ row.value }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePreferencesStore } from '@/store/preferences'

const props = defineProps({
  subscription: { type: Object, default: null },
  credits: { type: Object, default: null }
})

const { t } = useI18n()
const preferences = usePreferencesStore()

const planMetadata = computed(
  () =>
    props.subscription?.plan_metadata || props.credits?.plan_metadata || null
)

const rows = computed(() => [
  {
    key: 'emails',
    label: t('billing.creditsInfo.emailLimit'),
    value: `${
      planMetadata.value?.max_emails_per_period ||
      planMetadata.value?.credits_per_period ||
      '-'
    } ${t('billing.creditsInfo.emails')}`
  },
  {
    key: 'attachments',
    label: t('billing.creditsInfo.attachmentLimit'),
    value: `${planMetadata.value?.max_attachment_count || '-'} ${t(
      'billing.creditsInfo.attachments'
    )}`
  },
  {
    key: 'storage',
    label: t('billing.creditsInfo.storageQuota'),
    value: formatStorage(planMetadata.value?.storage_quota_mb)
  },
  {
    key: 'retention',
    label: t('billing.creditsInfo.retentionPeriod'),
    value: formatRetention(planMetadata.value?.retention_days)
  }
])

function formatStorage(storageMb) {
  if (!storageMb) return '-'
  if (storageMb >= 1024) return `${(storageMb / 1024).toFixed(0)} GB`
  return `${storageMb} MB`
}

function formatRetention(retentionDays) {
  if (retentionDays === null || retentionDays === undefined) {
    return t('billing.creditsInfo.retentionNotSet')
  }
  // -1 is the plan saying "we keep it", not a count of days.
  if (retentionDays === -1) return t('billing.creditsInfo.retentionPermanent')
  if (retentionDays >= 365) {
    const years = Math.floor(retentionDays / 365)
    if (years === 1) {
      return preferences.currentLanguage === 'zh-CN' ? '1年' : '1 year'
    }
    return t('billing.creditsInfo.retentionYears', { years })
  }
  return t('billing.creditsInfo.retentionDays', { days: retentionDays })
}
</script>
