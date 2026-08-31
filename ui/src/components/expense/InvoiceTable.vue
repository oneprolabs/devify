<template>
  <div class="overflow-x-auto">
    <p v-if="!invoices.length" class="py-8 text-center text-sm text-gray-500">
      {{ t('expense.invoices.empty') }}
    </p>

    <table v-else class="min-w-full text-sm">
      <thead>
        <tr class="border-b border-gray-200 text-left text-xs text-gray-500">
          <th v-if="selectable" class="w-8 py-2 pr-2">
            <input
              type="checkbox"
              class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              :checked="allClaimableSelected"
              :indeterminate.prop="someClaimableSelected"
              :aria-label="t('expense.invoices.selectAll')"
              @change="toggleAll($event.target.checked)"
            />
          </th>
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
          <td v-if="selectable" class="py-2 pr-2" @click.stop>
            <input
              type="checkbox"
              class="rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-40"
              :checked="modelValue.includes(invoice.uuid)"
              :disabled="!isClaimable(invoice)"
              :title="
                isClaimable(invoice) ? '' : t('expense.invoices.notClaimable')
              "
              @change="toggleOne(invoice, $event.target.checked)"
            />
          </td>
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
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  invoices: {
    type: Array,
    default: () => []
  },
  selectable: {
    type: Boolean,
    default: false
  },
  modelValue: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['select', 'update:modelValue'])

const { t } = useI18n()

// Only a recognized invoice can be claimed; duplicates and failures are
// visible but not selectable, so the reason is obvious before the server
// has to explain it.
function isClaimable(invoice) {
  return invoice.status === 'extracted'
}

const claimable = computed(() => props.invoices.filter(isClaimable))

const allClaimableSelected = computed(
  () =>
    claimable.value.length > 0 &&
    claimable.value.every((invoice) => props.modelValue.includes(invoice.uuid))
)

const someClaimableSelected = computed(
  () =>
    !allClaimableSelected.value &&
    claimable.value.some((invoice) => props.modelValue.includes(invoice.uuid))
)

function toggleOne(invoice, checked) {
  const next = new Set(props.modelValue)
  if (checked) {
    next.add(invoice.uuid)
  } else {
    next.delete(invoice.uuid)
  }
  emit('update:modelValue', [...next])
}

function toggleAll(checked) {
  if (!checked) {
    emit('update:modelValue', [])
    return
  }
  emit(
    'update:modelValue',
    claimable.value.map((invoice) => invoice.uuid)
  )
}

function formatAmount(invoice) {
  if (invoice.total_amount === null || invoice.total_amount === undefined) {
    return '-'
  }
  return `${invoice.currency || 'CNY'} ${invoice.total_amount}`
}
</script>
