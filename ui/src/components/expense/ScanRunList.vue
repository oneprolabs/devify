<template>
  <BaseCard>
    <div class="space-y-4">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-semibold text-ink">
            {{ t('expense.scan.historyTitle') }}
          </h2>
          <p class="mt-1 text-sm text-ink-3">
            {{ t('expense.scan.historySubtitle') }}
          </p>
        </div>
        <BaseButton size="sm" :loading="scanning" @click="$emit('scan')">
          {{ t('expense.scan.action') }}
        </BaseButton>
      </div>

      <p v-if="!runs.length" class="py-6 text-center text-sm text-ink-3">
        {{ t('expense.scan.empty') }}
      </p>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="border-b border-line text-left text-xs text-ink-3">
              <th class="py-2 pr-4 font-medium">
                {{ t('expense.scan.startedAt') }}
              </th>
              <th class="py-2 pr-4 font-medium">
                {{ t('expense.scan.trigger') }}
              </th>
              <th class="py-2 pr-4 font-medium">
                {{ t('expense.scan.status') }}
              </th>
              <th class="py-2 pr-4 text-right font-medium">
                {{ t('expense.scan.scanned') }}
              </th>
              <th class="py-2 pr-4 text-right font-medium">
                {{ t('expense.scan.candidates') }}
              </th>
              <th class="py-2 pr-4 text-right font-medium">
                {{ t('expense.scan.invoices') }}
              </th>
              <th class="py-2 text-right font-medium">
                {{ t('expense.scan.credits') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="run in runs"
              :key="run.uuid"
              class="border-b border-line-soft last:border-0"
            >
              <td class="py-2 pr-4 text-ink">
                {{ formatTime(run.started_at) }}
              </td>
              <td class="py-2 pr-4 text-ink-2">
                {{ t(`expense.scan.triggers.${run.trigger}`) }}
              </td>
              <td class="py-2 pr-4">
                <span
                  class="inline-flex rounded-full px-2 py-0.5 text-xs"
                  :class="statusClass(run.status)"
                >
                  {{ t(`expense.scan.statuses.${run.status}`) }}
                </span>
              </td>
              <td class="py-2 pr-4 text-right tabular-nums text-ink">
                {{ run.emails_scanned }}
              </td>
              <td class="py-2 pr-4 text-right tabular-nums text-ink">
                {{ run.candidate_emails }}
              </td>
              <td class="py-2 pr-4 text-right tabular-nums text-ink">
                {{ run.invoices_created }}
                <span
                  v-if="run.duplicates"
                  class="ml-1 text-xs text-ink-4"
                  :title="t('expense.scan.duplicates')"
                >
                  +{{ run.duplicates }}
                </span>
              </td>
              <td class="py-2 text-right tabular-nums text-ink">
                {{ run.credits_consumed }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </BaseCard>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'

defineProps({
  runs: {
    type: Array,
    default: () => []
  },
  scanning: {
    type: Boolean,
    default: false
  }
})

defineEmits(['scan'])

const { t, locale } = useI18n()

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString(locale.value)
}

function statusClass(status) {
  if (status === 'completed') return 'bg-ok-soft text-ok'
  if (status === 'failed') return 'bg-bad-soft text-bad'
  return 'bg-chip text-ink-2'
}
</script>
