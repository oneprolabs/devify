<template>
  <BaseCard>
    <div class="space-y-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h3 class="text-base font-semibold text-ink">
            {{ group.name }}
          </h3>
          <p class="mt-1 text-sm text-ink-3">
            {{
              t('expense.groups.line', {
                count: group.invoice_count,
                amount: group.total_amount
              })
            }}
            <template v-if="group.period_start">
              · {{ group.period_start }} ~ {{ group.period_end }}
            </template>
          </p>
        </div>
        <BaseButton size="sm" variant="secondary" @click="$emit('close')">
          {{ t('common.collapse') }}
        </BaseButton>
      </div>

      <p
        v-if="error"
        class="rounded-lg border border-bad bg-bad-soft p-3 text-sm text-bad"
      >
        {{ error }}
      </p>

      <!-- One scrolling panel rather than sub-tabs: a claim is small
           enough to read whole, and the figures and the invoices they
           come from are checked against each other. -->
      <section>
        <h4
          class="border-b border-line-soft pb-2 text-xs font-medium uppercase tracking-wide text-ink-3"
        >
          {{ t('expense.groups.formFields') }}
        </h4>
        <GroupSummaryPanel v-if="summary" :summary="summary" class="mt-3" />
      </section>

      <section>
        <div
          class="flex items-center justify-between border-b border-line-soft pb-2"
        >
          <h4 class="text-xs font-medium uppercase tracking-wide text-ink-3">
            {{ t('expense.groups.viewItems') }}
          </h4>
          <p class="text-xs text-ink-4">
            {{ t('expense.groups.sectionsHint') }}
          </p>
        </div>

        <p v-if="!sections.length" class="py-6 text-center text-sm text-ink-3">
          {{ t('expense.groups.noInvoices') }}
        </p>

        <!-- A claim form is filled one category at a time, so the invoices
             are laid out the way the form asks for them. -->
        <div v-for="section in sections" :key="section.category" class="mt-4">
          <div class="flex items-baseline justify-between">
            <strong class="text-sm text-ink">{{ section.label }}</strong>
            <span class="text-xs tabular-nums text-ink-3">
              {{
                t('expense.groups.sectionSummary', {
                  count: section.count,
                  amount: section.amount
                })
              }}
            </span>
          </div>

          <div
            v-for="invoice in section.invoices"
            :key="invoice.uuid"
            class="flex items-center justify-between gap-3 border-b border-line-soft py-2 last:border-0"
          >
            <div class="min-w-0">
              <p class="truncate text-sm text-ink">
                {{ invoice.seller_name || t('expense.invoices.untitled') }}
              </p>
              <p class="mt-0.5 truncate text-xs text-ink-3">
                {{ invoice.expense_date || invoice.issue_date || '-' }}
                <template v-if="invoice.summary_line">
                  · {{ invoice.summary_line }}
                </template>
              </p>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-sm tabular-nums text-ink">
                ¥{{ invoice.total_amount }}
              </span>
              <BaseButton
                size="sm"
                variant="outline"
                @click="$emit('move', invoice)"
              >
                {{ t('expense.groups.moveItem') }}
              </BaseButton>
              <BaseButton
                size="sm"
                variant="secondary"
                :loading="removing === invoice.uuid"
                @click="$emit('remove', invoice)"
              >
                {{ t('expense.groups.removeItem') }}
              </BaseButton>
            </div>
          </div>
        </div>
      </section>

      <section>
        <h4
          class="border-b border-line-soft pb-2 text-xs font-medium uppercase tracking-wide text-ink-3"
        >
          {{ t('expense.groups.exportSection') }}
        </h4>
        <div
          class="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-3"
        >
          <div>
            <p class="text-sm font-medium text-ink">
              {{ t('expense.groups.exportZip') }}
            </p>
            <p class="mt-0.5 text-xs text-ink-3">
              {{ t('expense.groups.exportZipHint') }}
            </p>
          </div>
          <BaseButton
            size="sm"
            :loading="exporting"
            @click="$emit('export', group)"
          >
            {{ t('expense.groups.export') }}
          </BaseButton>
        </div>
      </section>
    </div>
  </BaseCard>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import GroupSummaryPanel from '@/components/expense/GroupSummaryPanel.vue'

defineProps({
  group: {
    type: Object,
    required: true
  },
  summary: {
    type: Object,
    default: null
  },
  sections: {
    type: Array,
    default: () => []
  },
  removing: {
    type: String,
    default: ''
  },
  exporting: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

defineEmits(['close', 'remove', 'move', 'export'])

const { t } = useI18n()
</script>
