<template>
  <div class="space-y-4">
    <div
      class="grid grid-cols-2 gap-3 rounded-lg bg-gray-50 p-4 sm:grid-cols-4"
    >
      <div v-for="stat in stats" :key="stat.key">
        <dt class="text-xs text-gray-500">
          {{ t(`expense.groups.${stat.key}`) }}
        </dt>
        <dd class="mt-1 text-sm font-medium tabular-nums text-gray-900">
          {{ stat.value }}
        </dd>
      </div>
    </div>

    <div>
      <div class="mb-2 flex items-center justify-between">
        <h3 class="text-sm font-medium text-gray-900">
          {{ t('expense.groups.formFields') }}
        </h3>
        <BaseButton size="sm" variant="outline" @click="copyAll">
          {{
            copied ? t('expense.groups.copied') : t('expense.groups.copyAll')
          }}
        </BaseButton>
      </div>
      <pre
        class="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-gray-200 bg-white p-3 text-xs leading-relaxed text-gray-800"
        >{{ summary.text_block }}</pre
      >
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps({
  summary: {
    type: Object,
    required: true
  }
})

const { t } = useI18n()
const copied = ref(false)

const stats = computed(() => [
  { key: 'invoiceCount', value: props.summary.invoice_count },
  { key: 'totalAmount', value: props.summary.total_amount },
  { key: 'taxAmount', value: props.summary.tax_amount },
  { key: 'amountInWords', value: props.summary.total_amount_cn }
])

async function copyAll() {
  try {
    await navigator.clipboard.writeText(props.summary.text_block || '')
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    // Clipboard access can be refused; the text stays selectable above.
    copied.value = false
  }
}
</script>
