<template>
  <BaseCard>
    <div class="space-y-4">
      <div>
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('expense.invoices.title') }}
        </h2>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('expense.invoices.subtitle') }}
        </p>
      </div>

      <InvoiceFilters v-model="filters" />

      <p
        v-if="error"
        class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        {{ error }}
      </p>

      <div
        v-if="selectedUuids.length"
        class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary-200 bg-primary-50 p-3"
      >
        <span class="text-sm text-primary-900">
          {{
            t('expense.invoices.selectedCount', {
              count: selectedUuids.length
            })
          }}
        </span>
        <div class="flex gap-2">
          <BaseButton size="sm" variant="secondary" @click="selectedUuids = []">
            {{ t('expense.invoices.clearSelection') }}
          </BaseButton>
          <BaseButton size="sm" @click="addOpen = true">
            {{ t('expense.groups.addAction') }}
          </BaseButton>
        </div>
      </div>

      <InvoiceTable
        v-model="selectedUuids"
        :invoices="invoices"
        selectable
        @select="open"
      />
    </div>
  </BaseCard>

  <AddToGroupDialog
    v-if="addOpen"
    :invoice-uuids="selectedUuids"
    @close="addOpen = false"
    @added="onAdded"
  />

  <InvoiceDetailDrawer
    v-if="selected"
    :invoice="selected"
    :saving="saving"
    :reextracting="reextracting"
    :error="drawerError"
    @close="selected = null"
    @save="save"
    @reextract="reextract"
  />
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import AddToGroupDialog from '@/components/expense/AddToGroupDialog.vue'
import InvoiceDetailDrawer from '@/components/expense/InvoiceDetailDrawer.vue'
import InvoiceFilters from '@/components/expense/InvoiceFilters.vue'
import InvoiceTable from '@/components/expense/InvoiceTable.vue'
import { expenseApi } from '@/api/expense'

const emit = defineEmits(['rescanned', 'grouped'])

const { t } = useI18n()

const invoices = ref([])
const selectedUuids = ref([])
const addOpen = ref(false)
const selected = ref(null)
const saving = ref(false)
const reextracting = ref(false)
const error = ref('')
const drawerError = ref('')
const filters = ref({
  q: '',
  category: '',
  start: '',
  end: '',
  needsReview: false
})

function readError(err, fallbackKey) {
  return err?.response?.data?.message || t(fallbackKey)
}

function queryParams() {
  const params = {}
  if (filters.value.q) params.q = filters.value.q
  if (filters.value.category) params.category = filters.value.category
  if (filters.value.start) params.start = filters.value.start
  if (filters.value.end) params.end = filters.value.end
  if (filters.value.needsReview) params.needs_review = 'true'
  return params
}

async function load() {
  error.value = ''
  try {
    invoices.value = await expenseApi.getInvoices(queryParams())
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

async function open(row) {
  drawerError.value = ''
  try {
    selected.value = await expenseApi.getInvoice(row.uuid)
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

async function save(form) {
  saving.value = true
  drawerError.value = ''
  try {
    selected.value = await expenseApi.updateInvoice(selected.value.uuid, form)
    await load()
  } catch (err) {
    drawerError.value = readError(err, 'expense.invoices.saveFailed')
  } finally {
    saving.value = false
  }
}

// Reading an email again is billable, so it stays an explicit action
// rather than something the drawer does when it opens.
async function reextract(invoice) {
  reextracting.value = true
  drawerError.value = ''
  try {
    await expenseApi.reextractInvoice(invoice.uuid)
    selected.value = null
    emit('rescanned')
  } catch (err) {
    drawerError.value = readError(err, 'expense.invoices.saveFailed')
  } finally {
    reextracting.value = false
  }
}

async function onAdded() {
  addOpen.value = false
  selectedUuids.value = []
  await load()
  // The group totals changed, so whoever owns that list needs to know.
  emit('grouped')
}

watch(filters, load, { deep: true })
onMounted(load)

defineExpose({ load })
</script>
