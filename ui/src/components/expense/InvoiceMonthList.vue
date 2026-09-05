<template>
  <div>
    <p v-if="!invoices.length" class="py-10 text-center text-sm text-ink-3">
      {{ t('expense.invoices.empty') }}
    </p>

    <div v-for="month in months" :key="month.key">
      <div
        class="flex h-9 items-center gap-2 border-y border-line bg-panel-sub px-4 md:px-5"
      >
        <span
          class="font-display text-[calc(11.5px*var(--fs))] font-semibold tracking-[0.02em] text-ink"
        >
          {{ month.label }}
        </span>
        <span class="font-mono text-[calc(10.5px*var(--fs))] text-ink-4">
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
        class="flex cursor-pointer items-start gap-3 border-b border-line-soft px-4 py-[var(--rowpy)] transition-colors hover:bg-panel-sub md:px-5"
        @click="$emit('select', invoice)"
      >
        <input
          v-if="selectable"
          type="checkbox"
          class="mt-0.5 h-[17px] w-[17px] flex-none rounded-sm border-line text-accent focus:ring-accent disabled:opacity-40"
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

        <div class="flex min-w-0 flex-1 flex-col gap-[3px]">
          <p class="truncate text-[calc(13.5px*var(--fs))] font-medium text-ink">
            {{ invoice.seller_name || t('expense.invoices.untitled') }}
          </p>
          <p
            v-if="invoice.buyer_name"
            class="flex items-center gap-1.5 text-[calc(11.5px*var(--fs))] text-ink-3"
          >
            <span
              class="flex-none rounded-sm px-1.5 py-px text-[calc(10.5px*var(--fs))]"
              :class="
                invoice.buyer_tax_id
                  ? 'bg-accent-soft text-accent'
                  : 'bg-chip text-ink-2'
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
            class="truncate text-[calc(11.5px*var(--fs))] text-ink-3"
          >
            {{ invoice.summary_line }}
          </p>
          <div class="flex flex-wrap items-center gap-1.5 pt-0.5">
            <span
              class="rounded-full bg-chip px-[9px] py-0.5 text-[calc(10.5px*var(--fs))] text-ink-2"
            >
              {{ t(`expense.categories.${invoice.category || 'other'}`) }}
            </span>
            <span
              v-if="invoice.status === 'duplicate'"
              class="rounded-full bg-chip px-[9px] py-0.5 text-[calc(10.5px*var(--fs))] text-ink-2"
            >
              {{ t('expense.invoices.duplicate') }}
            </span>
            <span
              v-if="invoice.needs_review"
              class="rounded-full bg-warn-soft px-[9px] py-0.5 text-[calc(10.5px*var(--fs))] text-warn"
            >
              {{ t('expense.invoices.needsReview') }}
            </span>
            <span
              v-if="invoice.status === 'failed'"
              class="rounded-full bg-bad-soft px-[9px] py-0.5 text-[calc(10.5px*var(--fs))] text-bad"
            >
              {{ t('expense.invoices.failed') }}
            </span>
            <span
              v-if="invoice.disposition === 'filed'"
              class="rounded-full bg-ok-soft px-[9px] py-0.5 text-[calc(10.5px*var(--fs))] text-ok"
            >
              {{
                t(
                  `expense.invoices.filedReasons.${invoice.filed_reason || 'other'}`
                )
              }}
            </span>
          </div>
        </div>

        <div class="flex w-[170px] flex-none flex-col items-end gap-[3px]">
          <p class="font-mono text-[calc(13.5px*var(--fs))] font-medium text-ink">
            {{ formatAmount(invoice) }}
          </p>
          <p class="text-right font-mono text-[calc(11px*var(--fs))] text-ink-3">
            {{ t('expense.invoices.spentOn') }}
            <b class="text-ink-2">{{ shortDate(effectiveDate(invoice)) }}</b>
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
              // The canvas writes the month without a leading zero.
              month: String(Number(key.slice(5)))
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
