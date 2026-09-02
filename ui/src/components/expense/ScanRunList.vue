<template>
  <BaseCard>
    <div class="space-y-4">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('expense.scan.historyTitle') }}
          </h2>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('expense.scan.historySubtitle') }}
          </p>
        </div>
        <BaseButton size="sm" :loading="scanning" @click="$emit('scan')">
          {{ t('expense.scan.action') }}
        </BaseButton>
      </div>

      <p v-if="!runs.length" class="py-6 text-center text-sm text-gray-500">
        {{ t('expense.scan.empty') }}
      </p>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr
              class="border-b border-gray-200 text-left text-xs text-gray-500"
            >
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
              class="border-b border-gray-100 last:border-0"
            >
              <td class="py-2 pr-4 text-gray-900">
                {{ formatTime(run.started_at) }}
              </td>
              <td class="py-2 pr-4 text-gray-600">
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
              <td class="py-2 pr-4 text-right tabular-nums text-gray-900">
                {{ run.emails_scanned }}
              </td>
              <td class="py-2 pr-4 text-right tabular-nums text-gray-900">
                {{ run.candidate_emails }}
              </td>
              <td class="py-2 pr-4 text-right tabular-nums text-gray-900">
                {{ run.invoices_created }}
                <span
                  v-if="run.duplicates"
                  class="ml-1 text-xs text-gray-400"
                  :title="t('expense.scan.duplicates')"
                >
                  +{{ run.duplicates }}
                </span>
              </td>
              <td class="py-2 text-right tabular-nums text-gray-900">
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
  if (status === 'completed') return 'bg-green-100 text-green-700'
  if (status === 'failed') return 'bg-red-100 text-red-700'
  return 'bg-gray-100 text-gray-600'
}
</script>
