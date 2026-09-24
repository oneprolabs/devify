<template>
  <!-- One batch in full, filling the right of the workbench. The artboard
       orders it deliberately: the claim-form figures come before the
       invoices, because copying those four numbers into the company's form
       is what the reader actually came to do. -->
  <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
    <div
      class="flex flex-none items-start gap-3 border-b border-line px-5 pb-[13px] pt-4"
    >
      <button
        v-if="canGoBack"
        type="button"
        class="-ml-1 flex-none self-center text-ink transition-colors hover:text-ink-2 md:hidden"
        :aria-label="t('common.back')"
        @click="$emit('back')"
      >
        <svg
          class="h-5 w-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            d="M15 5l-7 7 7 7"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>

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

      <div class="ml-auto hidden flex-none items-center gap-2 md:flex">
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
      <div class="grid grid-cols-2 gap-3.5 md:contents">
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
      </div>

      <div
        class="mt-3.5 flex flex-col items-stretch gap-1.5 border-t border-line-soft pt-3.5 md:ml-auto md:mt-0 md:items-end md:border-0 md:pt-0"
      >
        <BaseButton size="sm" variant="outline" @click="copyAll">
          {{
            copied ? t('expense.groups.copied') : t('expense.groups.copyAll')
          }}
        </BaseButton>
        <span
          class="text-center text-[calc(10.5px*var(--fs))] text-ink-4 md:text-right"
        >
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
                amount: formatAmount(section.amount)
              })
            }}
          </span>
          <span class="ml-auto text-[calc(11px*var(--fs))] text-ink-3">
            <span class="md:hidden">
              {{ t('expense.groups.perLineShort') }}
            </span>
            <span class="hidden md:inline">
              {{ t('expense.groups.perLine') }}
            </span>
          </span>
        </div>

        <div
          v-for="invoice in section.invoices"
          :key="invoice.uuid"
          class="border-b border-line-soft last:border-b-0"
        >
          <!-- Checking a claim line by line means wanting to see the
               invoice behind one: the original, the fields, whether the
               amount is what the row says. Without this the only way
               there was to leave the group, find it in the list and
               search for it again. -->
          <div
            class="flex cursor-pointer items-center gap-3 px-[13px] py-[11px] transition-colors hover:bg-panel-sub"
            role="button"
            tabindex="0"
            @click="$emit('open', invoice)"
            @keyup.enter="$emit('open', invoice)"
          >
            <!-- One line of columns is what 1440 affords. A phone stacks the
                 seller over its number and date instead, and moves the two
                 corrections behind the overflow dots. -->
            <div
              class="flex min-w-0 flex-1 flex-col gap-0.5 md:flex-row md:items-center md:gap-3"
            >
              <span
                class="truncate text-[calc(12.5px*var(--fs))] text-ink md:flex-1"
              >
                {{ invoice.seller_name || t('expense.invoices.untitled') }}
              </span>
              <span
                class="font-mono truncate text-[calc(10px*var(--fs))] text-ink-4 md:hidden"
              >
                {{ invoice.invoice_no }} ·
                {{ shortDate(invoice.expense_date || invoice.issue_date) }}
              </span>
              <span
                class="font-mono hidden w-[150px] flex-none truncate text-[calc(10.5px*var(--fs))] text-ink-4 lg:block"
              >
                {{ invoice.invoice_no }}
              </span>
              <span
                class="font-mono hidden w-[52px] flex-none text-[calc(11px*var(--fs))] text-ink-3 md:block"
              >
                {{ shortDate(invoice.expense_date || invoice.issue_date) }}
              </span>
            </div>

            <span
              class="font-mono w-[84px] flex-none text-right text-[calc(12.5px*var(--fs))] font-medium text-ink"
            >
              ¥{{ formatAmount(invoice.total_amount) }}
            </span>

            <span class="hidden w-[96px] flex-none justify-end gap-1.5 md:flex">
              <button
                type="button"
                class="text-[calc(11px*var(--fs))] text-ink-3 transition-colors hover:text-ink disabled:opacity-50"
                :disabled="removing === invoice.uuid"
                @click.stop="$emit('remove', invoice)"
              >
                {{ t('expense.groups.remove') }}
              </button>
              <span class="text-[calc(11px*var(--fs))] text-ink-4">·</span>
              <button
                type="button"
                class="text-[calc(11px*var(--fs))] text-ink-3 transition-colors hover:text-ink"
                @click.stop="$emit('move', invoice)"
              >
                {{ t('expense.groups.moveTo') }}
              </button>
            </span>

            <button
              type="button"
              class="flex-none text-ink-3 transition-colors hover:text-ink md:hidden"
              :aria-label="t('common.more')"
              :aria-expanded="openRow === invoice.uuid"
              @click.stop="
                openRow = openRow === invoice.uuid ? '' : invoice.uuid
              "
            >
              <svg
                class="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <circle cx="12" cy="5" r="1.4" />
                <circle cx="12" cy="12" r="1.4" />
                <circle cx="12" cy="19" r="1.4" />
              </svg>
            </button>
          </div>

          <div
            v-if="openRow === invoice.uuid"
            class="flex items-center justify-end gap-4 bg-panel-sub px-[13px] py-2.5 md:hidden"
          >
            <button
              type="button"
              class="text-[calc(12px*var(--fs))] text-ink-2 disabled:opacity-50"
              :disabled="removing === invoice.uuid"
              @click.stop="$emit('remove', invoice)"
            >
              {{ t('expense.groups.remove') }}
            </button>
            <button
              type="button"
              class="text-[calc(12px*var(--fs))] text-ink-2"
              @click.stop="$emit('move', invoice)"
            >
              {{ t('expense.groups.moveTo') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- The header has no room for these on a phone, so the artboard puts
         them in a bar at the bottom, where the thumb already is. -->
    <div
      class="flex flex-none items-center gap-2.5 border-t border-line px-4 py-3 md:hidden"
    >
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
        class="flex-1 justify-center"
        :loading="exporting"
        @click="$emit('export', group)"
      >
        {{ t('expense.groups.export') }}
      </BaseButton>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import { formatAmount } from '@/utils/formatting'

const props = defineProps({
  group: { type: Object, required: true },
  summary: { type: Object, required: true },
  sections: { type: Array, default: () => [] },
  removing: { type: String, default: '' },
  exporting: { type: Boolean, default: false },
  settling: { type: Boolean, default: false },
  error: { type: String, default: '' },
  // A phone reaches a batch from the list, so it needs the way back.
  canGoBack: { type: Boolean, default: false }
})

defineEmits(['remove', 'move', 'export', 'settle', 'back', 'open'])

const { t } = useI18n()
const copied = ref(false)
// Which row has its corrections open; phones only, one at a time.
const openRow = ref('')

const stats = computed(() => [
  { key: 'invoiceCount', value: props.summary.invoice_count },
  { key: 'totalAmount', value: `¥${formatAmount(props.summary.total_amount)}` },
  { key: 'taxAmount', value: `¥${formatAmount(props.summary.tax_amount)}` },
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
