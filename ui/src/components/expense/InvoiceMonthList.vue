<template>
  <div>
    <p v-if="!invoices.length" class="py-10 text-center text-sm text-gray-500">
      {{ t('expense.invoices.empty') }}
    </p>

    <div v-for="month in months" :key="month.key" class="mb-2 last:mb-0">
      <div
        class="flex items-baseline justify-between border-b border-gray-100 px-1 py-2"
      >
        <strong class="text-sm text-gray-900">{{ month.label }}</strong>
        <span class="text-xs tabular-nums text-gray-500">
          {{
            t('expense.invoices.monthSummary', {
              count: month.invoices.length,
              amount: month.amount
            })
          }}
        </span>
      </div>

      <div
        v-for="invoice in month.invoices"
        :key="invoice.uuid"
        class="grid cursor-pointer grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 border-b border-gray-50 px-1 py-3 last:border-0 hover:bg-gray-50"
        @click="$emit('select', invoice)"
      >
        <input
          v-if="selectable"
          type="checkbox"
          class="mt-1 rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-40"
          :checked="modelValue.includes(invoice.uuid)"
          :disabled="!isClaimable(invoice)"
          :title="
            isClaimable(invoice) ? '' : t('expense.invoices.notClaimable')
          "
          :aria-label="invoice.seller_name"
          @click.stop
          @change="toggleOne(invoice, $event.target.checked)"
        />
        <span v-else></span>

        <div class="min-w-0">
          <p class="truncate text-sm font-medium text-gray-900">
            {{ invoice.seller_name || t('expense.invoices.untitled') }}
          </p>
          <p
            v-if="invoice.buyer_name"
            class="mt-0.5 flex items-center gap-1.5 text-xs text-gray-500"
          >
            <span
              class="rounded px-1.5 py-0.5 text-[11px]"
              :class="
                invoice.buyer_tax_id
                  ? 'bg-primary-50 text-primary-700'
                  : 'bg-gray-100 text-gray-600'
              "
            >
              {{
                invoice.buyer_tax_id
                  ? t('expense.invoices.titleCompany')
                  : t('expense.invoices.titlePersonal')
              }}
            </span>
            <span class="truncate">{{ invoice.buyer_name }}</span>
          </p>
          <p
            v-if="invoice.summary_line"
            class="mt-0.5 truncate text-xs text-gray-500"
          >
            {{ invoice.summary_line }}
          </p>
          <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
            <span
              class="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-700"
            >
              {{ t(`expense.categories.${invoice.category || 'other'}`) }}
            </span>
            <span
              v-if="invoice.status === 'duplicate'"
              class="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600"
            >
              {{ t('expense.invoices.duplicate') }}
            </span>
            <span
              v-if="invoice.needs_review"
              class="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-800"
            >
              {{ t('expense.invoices.needsReview') }}
            </span>
            <span
              v-if="invoice.status === 'failed'"
              class="rounded-full bg-red-100 px-2 py-0.5 text-[11px] text-red-800"
            >
              {{ t('expense.invoices.failed') }}
            </span>
            <span
              v-if="invoice.disposition === 'filed'"
              class="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700"
            >
              {{
                t(
                  `expense.invoices.filedReasons.${invoice.filed_reason || 'other'}`
                )
              }}
            </span>
          </div>
        </div>

        <div class="text-right">
          <p class="text-sm font-medium tabular-nums text-gray-900">
            {{ formatAmount(invoice) }}
          </p>
          <p class="mt-0.5 text-xs tabular-nums text-gray-500">
            {{ t('expense.invoices.spentOn') }}
            <b class="text-gray-700">{{ shortDate(effectiveDate(invoice)) }}</b>
            <template v-if="showsBothDates(invoice)">
              · {{ t('expense.invoices.issuedOn') }}
              {{ shortDate(invoice.issue_date) }}
            </template>
          </p>
        </div>
      </div>
    </div>
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

// When the money was spent, not when the invoice was cut: a July train
// ticket billed in August belongs to July on a claim form.
function effectiveDate(invoice) {
  return invoice.expense_date || invoice.issue_date || ''
}

// Repeating the same date twice is noise; the pair only matters when the
// two differ, which is exactly when it is worth explaining.
function showsBothDates(invoice) {
  return invoice.issue_date && invoice.issue_date !== effectiveDate(invoice)
}

function shortDate(value) {
  return value ? value.slice(5) : '-'
}

const months = computed(() => {
  const buckets = new Map()
  props.invoices.forEach((invoice) => {
    const date = effectiveDate(invoice)
    const key = date ? date.slice(0, 7) : 'unknown'
    if (!buckets.has(key)) buckets.set(key, [])
    buckets.get(key).push(invoice)
  })

  return [...buckets.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([key, invoices]) => ({
      key,
      label:
        key === 'unknown'
          ? t('expense.invoices.noDate')
          : t('expense.invoices.monthLabel', {
              year: key.slice(0, 4),
              month: key.slice(5)
            }),
      invoices,
      amount: invoices
        .reduce((sum, invoice) => sum + Number(invoice.total_amount || 0), 0)
        .toFixed(2)
    }))
})

// Only a recognized invoice can be claimed; duplicates and failures stay
// visible but not selectable, so the reason is obvious before the server
// has to explain it.
function isClaimable(invoice) {
  return invoice.status === 'extracted'
}

function toggleOne(invoice, checked) {
  const next = new Set(props.modelValue)
  if (checked) {
    next.add(invoice.uuid)
  } else {
    next.delete(invoice.uuid)
  }
  emit('update:modelValue', [...next])
}

function formatAmount(invoice) {
  if (invoice.total_amount === null || invoice.total_amount === undefined) {
    return '-'
  }
  const symbol = (invoice.currency || 'CNY') === 'CNY' ? '¥' : ''
  return symbol
    ? `${symbol}${invoice.total_amount}`
    : `${invoice.currency} ${invoice.total_amount}`
}
</script>
