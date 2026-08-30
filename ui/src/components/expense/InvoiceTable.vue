<template>
  <div class="overflow-x-auto">
    <p v-if="!invoices.length" class="py-8 text-center text-sm text-gray-500">
      {{ t('expense.invoices.empty') }}
    </p>

    <table v-else class="min-w-full text-sm">
      <thead>
        <tr class="border-b border-gray-200 text-left text-xs text-gray-500">
          <th class="py-2 pr-4 font-medium">
            {{ t('expense.invoices.issueDate') }}
          </th>
          <th class="py-2 pr-4 font-medium">
            {{ t('expense.invoices.seller') }}
          </th>
          <th class="py-2 pr-4 font-medium">
            {{ t('expense.invoices.category') }}
          </th>
          <th class="py-2 pr-4 text-right font-medium">
            {{ t('expense.invoices.amount') }}
          </th>
          <th class="py-2 font-medium">
            {{ t('expense.invoices.state') }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="invoice in invoices"
          :key="invoice.uuid"
          class="cursor-pointer border-b border-gray-100 last:border-0 hover:bg-gray-50"
          @click="$emit('select', invoice)"
        >
          <td class="py-2 pr-4 tabular-nums text-gray-900">
            {{ invoice.issue_date || '-' }}
          </td>
          <td class="max-w-[16rem] truncate py-2 pr-4 text-gray-900">
            {{ invoice.seller_name || '-' }}
          </td>
          <td class="py-2 pr-4 text-gray-600">
            {{ t(`expense.categories.${invoice.category || 'other'}`) }}
          </td>
          <td class="py-2 pr-4 text-right tabular-nums text-gray-900">
            {{ formatAmount(invoice) }}
          </td>
          <td class="py-2">
            <span
              v-if="invoice.status === 'duplicate'"
              class="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
            >
              {{ t('expense.invoices.duplicate') }}
            </span>
            <span
              v-else-if="invoice.needs_review"
              class="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
            >
              {{ t('expense.invoices.needsReview') }}
            </span>
            <span v-else class="text-xs text-gray-400">
              {{ t('expense.invoices.ok') }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  invoices: {
    type: Array,
    default: () => []
  }
})

defineEmits(['select'])

const { t } = useI18n()

function formatAmount(invoice) {
  if (invoice.total_amount === null || invoice.total_amount === undefined) {
    return '-'
  }
  return `${invoice.currency || 'CNY'} ${invoice.total_amount}`
}
</script>
