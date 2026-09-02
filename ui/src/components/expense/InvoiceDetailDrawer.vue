<template>
  <div class="fixed inset-0 z-40 flex justify-end" @click.self="$emit('close')">
    <div class="absolute inset-0 bg-gray-500 bg-opacity-50"></div>

    <aside
      class="relative z-10 flex h-full w-full max-w-xl flex-col overflow-y-auto bg-white shadow-xl"
    >
      <header
        class="flex items-start justify-between gap-4 border-b border-gray-200 p-5"
      >
        <div class="min-w-0">
          <h2 class="truncate text-lg font-semibold text-gray-900">
            {{ form.seller_name || t('expense.invoices.untitled') }}
          </h2>
          <p class="mt-1 truncate text-xs text-gray-500">
            {{ invoice.email_subject }}
          </p>
        </div>
        <button
          type="button"
          class="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          :aria-label="t('common.close')"
          @click="$emit('close')"
        >
          <svg
            class="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </header>

      <div class="flex-1 space-y-5 p-5">
        <p
          v-if="invoice.needs_review"
          class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
        >
          {{ t('expense.invoices.reviewHint') }}
        </p>

        <p
          v-if="error"
          class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          {{ error }}
        </p>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label v-for="field in textFields" :key="field.key" class="block">
            <span class="mb-1 block text-xs text-gray-500">
              {{ t(`expense.invoices.fields.${field.key}`) }}
            </span>
            <input
              v-model="form[field.key]"
              :type="field.type || 'text'"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </label>

          <label class="block">
            <span class="mb-1 block text-xs text-gray-500">
              {{ t('expense.invoices.category') }}
            </span>
            <select
              v-model="form.category"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            >
              <option v-for="key in categories" :key="key" :value="key">
                {{ t(`expense.categories.${key}`) }}
              </option>
            </select>
            <span class="mt-1 block text-xs text-gray-400">
              {{
                t(
                  `expense.invoices.sources.${invoice.category_source || 'model'}`
                )
              }}
            </span>
          </label>
        </div>

        <p class="text-xs leading-relaxed text-gray-500">
          {{ t('expense.invoices.learnHint') }}
        </p>

        <div
          v-if="invoice.status === 'failed' && invoice.error_message"
          class="space-y-1 rounded-lg border border-red-200 bg-red-50 p-3"
        >
          <p class="text-xs font-medium text-red-800">
            {{ t('expense.invoices.failedTitle') }}
          </p>
          <p class="text-xs leading-relaxed text-red-700">
            {{ invoice.error_message }}
          </p>
          <p class="text-xs leading-relaxed text-red-600">
            {{ t('expense.invoices.failedHint') }}
          </p>
        </div>

        <div class="space-y-2">
          <h3 class="text-sm font-medium text-gray-900">
            {{ t('expense.invoices.original') }}
          </h3>

          <p
            v-if="!invoice.has_file"
            class="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-500"
          >
            {{ t('expense.invoices.originalMissing') }}
          </p>

          <div
            v-else-if="fileLoading"
            class="h-64 animate-pulse rounded-lg bg-gray-100"
          ></div>

          <p
            v-else-if="fileError"
            class="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
          >
            {{ fileError }}
          </p>

          <img
            v-else-if="fileUrl && previewKind === 'image'"
            :src="fileUrl"
            :alt="t('expense.invoices.original')"
            class="w-full rounded-lg border border-gray-200"
          />

          <iframe
            v-else-if="fileUrl && previewKind === 'pdf'"
            :src="fileUrl"
            class="h-[32rem] w-full rounded-lg border border-gray-200"
            :title="t('expense.invoices.original')"
          ></iframe>

          <div
            v-else
            class="space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-3"
          >
            <p class="text-xs text-gray-500">
              {{ t('expense.invoices.originalNotViewable') }}
            </p>
            <a
              v-if="fileUrl"
              :href="fileUrl"
              :download="invoice.filename || 'invoice'"
              class="text-xs text-primary-600 hover:underline"
            >
              {{ t('expense.invoices.originalDownload') }}
            </a>
          </div>
        </div>

        <div
          v-if="invoice.ticket_details && hasTicketDetails"
          class="space-y-2"
        >
          <h3 class="text-sm font-medium text-gray-900">
            {{ t('expense.invoices.ticketDetails') }}
          </h3>
          <dl class="grid grid-cols-2 gap-2 rounded-lg bg-gray-50 p-3 text-xs">
            <template v-for="(value, key) in invoice.ticket_details" :key="key">
              <dt class="text-gray-500">{{ key }}</dt>
              <dd class="text-gray-900">{{ value }}</dd>
            </template>
          </dl>
        </div>
      </div>

      <footer
        class="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 p-5"
      >
        <BaseButton
          size="sm"
          variant="outline"
          :loading="reextracting"
          @click="$emit('reextract', invoice)"
        >
          {{ t('expense.invoices.reextract') }}
        </BaseButton>

        <BaseButton size="sm" :loading="saving" @click="$emit('save', form)">
          {{ t('common.save') }}
        </BaseButton>
      </footer>
    </aside>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import { expenseApi } from '@/api/expense'

const props = defineProps({
  invoice: {
    type: Object,
    required: true
  },
  saving: {
    type: Boolean,
    default: false
  },
  reextracting: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

defineEmits(['close', 'save', 'reextract'])

const { t } = useI18n()

const textFields = [
  { key: 'invoice_no' },
  { key: 'issue_date', type: 'date' },
  { key: 'seller_name' },
  { key: 'seller_tax_id' },
  { key: 'buyer_name' },
  { key: 'buyer_tax_id' },
  { key: 'total_amount' },
  { key: 'tax_amount' },
  { key: 'amount_excl_tax' },
  { key: 'city' }
]

const categories = [
  'transport_long',
  'transport_local',
  'accommodation',
  'meals',
  'entertainment',
  'office',
  'communication',
  'training',
  'other'
]

const form = reactive({})

function load(invoice) {
  textFields.forEach((field) => {
    form[field.key] = invoice[field.key] ?? ''
  })
  form.category = invoice.category || 'other'
}

watch(() => props.invoice, load, { immediate: true })

const hasTicketDetails = computed(
  () => Object.keys(props.invoice.ticket_details || {}).length > 0
)

const fileUrl = ref('')
const fileLoading = ref(false)
const fileError = ref('')

const previewKind = computed(() => {
  const type = (props.invoice.file_content_type || '').toLowerCase()
  if (type.startsWith('image/')) return 'image'
  if (type.includes('pdf')) return 'pdf'
  // OFD and anything else has no browser renderer; offer the file instead
  // of an empty frame.
  return 'other'
})

function releaseFile() {
  if (fileUrl.value) {
    URL.revokeObjectURL(fileUrl.value)
    fileUrl.value = ''
  }
}

async function loadFile(invoice) {
  releaseFile()
  fileError.value = ''
  if (!invoice?.has_file) return

  fileLoading.value = true
  try {
    const blob = await expenseApi.getInvoiceFile(invoice.uuid)
    fileUrl.value = URL.createObjectURL(blob)
  } catch (err) {
    fileError.value =
      err?.response?.data?.message || t('expense.invoices.originalFailed')
  } finally {
    fileLoading.value = false
  }
}

watch(
  () => props.invoice?.uuid,
  () => loadFile(props.invoice),
  {
    immediate: true
  }
)

onBeforeUnmount(releaseFile)
</script>
