<template>
  <!-- One batch in full, filling the right of the workbench. The artboard
       orders it deliberately: the claim-form figures come before the
       invoices, because copying those four numbers into the company's form
       is what the reader actually came to do. -->
  <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
    <div
      class="flex flex-none items-start gap-3 border-b border-line px-5 pb-[13px] pt-4"
    >
      <div class="flex min-w-0 flex-col gap-1">
        <div class="flex min-w-0 items-center gap-2">
          <h3
            class="truncate text-[calc(15px*var(--fs))] font-semibold -tracking-[0.01em] text-ink"
          >
            {{ group.name }}
          </h3>
          <span
            v-if="group.trip_type === 'business_trip'"
            class="font-mono flex-none rounded-sm border border-accent px-[5px] py-px text-[calc(9.5px*var(--fs))] text-accent"
          >
            {{ t('expense.groups.businessTrip') }}
          </span>
          <span
            class="font-mono flex-none rounded-sm px-1.5 py-0.5 text-[calc(9.5px*var(--fs))]"
            :class="
              group.status === 'draft'
                ? 'bg-warn-soft text-warn'
                : 'bg-panel-sub text-ink-3'
            "
          >
            {{ t(`expense.groups.statuses.${group.status}`) }}
          </span>
        </div>
        <span class="text-[calc(12px*var(--fs))] text-ink-3">
          {{ t('expense.groups.byCategory') }}
        </span>
      </div>

      <div class="ml-auto flex flex-none items-center gap-2">
        <BaseButton
          v-if="group.status === 'draft'"
          size="sm"
          variant="outline"
          :loading="settling"
          @click="$emit('settle', group)"
        >
          {{ t('expense.groups.markReimbursed') }}
        </BaseButton>
        <BaseButton
          size="sm"
          :loading="exporting"
          @click="$emit('export', group)"
        >
          {{ t('expense.groups.export') }}
        </BaseButton>
      </div>
    </div>

    <!-- The four numbers the claim form asks for, and one button that puts
         all of them on the clipboard. -->
    <div
      class="mx-5 mt-4 flex flex-none flex-wrap items-center gap-7 rounded-[9px] border border-line bg-panel-sub px-4 py-3.5"
    >
      <div
        v-for="stat in stats"
        :key="stat.key"
        class="flex flex-col gap-[3px]"
      >
        <span class="text-[calc(10.5px*var(--fs))] text-ink-3">
          {{ t(`expense.groups.${stat.key}`) }}
        </span>
        <span
          class="font-mono font-medium text-ink"
          :class="
            stat.key === 'amountInWords'
              ? 'text-[calc(13px*var(--fs))] font-normal'
              : 'text-[calc(17px*var(--fs))]'
          "
        >
          {{ stat.value }}
        </span>
      </div>

      <div class="ml-auto flex flex-col items-end gap-1.5">
        <BaseButton size="sm" variant="outline" @click="copyAll">
          {{
            copied ? t('expense.groups.copied') : t('expense.groups.copyAll')
          }}
        </BaseButton>
        <span class="text-[calc(10.5px*var(--fs))] text-ink-4">
          {{ t('expense.groups.copyHint') }}
        </span>
      </div>
    </div>

    <p
      v-if="error"
      class="mx-5 mt-3 flex-none rounded-lg border border-bad bg-bad-soft px-[13px] py-[11px] text-[calc(11.5px*var(--fs))] text-bad"
    >
      {{ error }}
    </p>

    <div
      class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-5 pb-5 pt-4"
    >
      <div
        v-for="section in sections"
        :key="section.category"
        class="flex-none overflow-hidden rounded-[9px] border border-line"
      >
        <div
          class="flex h-[34px] items-center gap-2 border-b border-line bg-panel-sub px-[13px]"
        >
          <span class="text-[calc(11.5px*var(--fs))] font-semibold text-ink">
            {{ section.label }}
          </span>
          <span class="font-mono text-[calc(10.5px*var(--fs))] text-ink-4">
            {{
              t('expense.groups.line', {
                count: section.count,
                amount: section.amount
              })
            }}
          </span>
          <span class="ml-auto text-[calc(11px*var(--fs))] text-ink-3">
            {{ t('expense.groups.perLine') }}
          </span>
        </div>

        <div
          v-for="invoice in section.invoices"
          :key="invoice.uuid"
          class="flex items-center gap-3 border-b border-line-soft px-[13px] py-[11px] last:border-b-0"
        >
          <span
            class="min-w-0 flex-1 truncate text-[calc(12.5px*var(--fs))] text-ink"
          >
            {{ invoice.seller_name || t('expense.invoices.untitled') }}
          </span>
          <span
            class="font-mono hidden w-[150px] flex-none truncate text-[calc(10.5px*var(--fs))] text-ink-4 lg:block"
          >
            {{ invoice.invoice_no }}
          </span>
          <span
            class="font-mono w-[52px] flex-none text-[calc(11px*var(--fs))] text-ink-3"
          >
            {{ shortDate(invoice.expense_date || invoice.issue_date) }}
          </span>
          <span
            class="font-mono w-[84px] flex-none text-right text-[calc(12.5px*var(--fs))] font-medium text-ink"
          >
            ¥{{ invoice.total_amount }}
          </span>
          <span class="flex w-[96px] flex-none justify-end gap-1.5">
            <button
              type="button"
              class="text-[calc(11px*var(--fs))] text-ink-3 transition-colors hover:text-ink disabled:opacity-50"
              :disabled="removing === invoice.uuid"
              @click="$emit('remove', invoice)"
            >
              {{ t('expense.groups.remove') }}
            </button>
            <span class="text-[calc(11px*var(--fs))] text-ink-4">·</span>
            <button
              type="button"
              class="text-[calc(11px*var(--fs))] text-ink-3 transition-colors hover:text-ink"
              @click="$emit('move', invoice)"
            >
              {{ t('expense.groups.moveTo') }}
            </button>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps({
  group: { type: Object, required: true },
  summary: { type: Object, required: true },
  sections: { type: Array, default: () => [] },
  removing: { type: String, default: '' },
  exporting: { type: Boolean, default: false },
  settling: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

defineEmits(['remove', 'move', 'export', 'settle'])

const { t } = useI18n()
const copied = ref(false)

const stats = computed(() => [
  { key: 'invoiceCount', value: props.summary.invoice_count },
  { key: 'totalAmount', value: `¥${props.summary.total_amount}` },
  { key: 'taxAmount', value: `¥${props.summary.tax_amount}` },
  { key: 'amountInWords', value: props.summary.total_amount_cn }
])

function shortDate(value) {
  return value ? value.slice(5) : '-'
}

async function copyAll() {
  try {
    await navigator.clipboard.writeText(props.summary.text_block || '')
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    // Clipboard access can be refused; nothing is lost, the figures are
    // on screen.
    copied.value = false
  }
}
</script>
