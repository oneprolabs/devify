<template>
  <div class="space-y-4">
    <FilterChips v-model="stage" :options="stageOptions" />

    <BaseCard>
      <div class="space-y-4">
        <InvoiceFilters v-model="filters" :buyers="buyers" />

        <p
          v-if="error"
          class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          {{ error }}
        </p>

        <!-- Filing something away is silent by nature: the row simply
             leaves the list. This says where it went and offers the way
             back, so the action never feels like a deletion. -->
        <div
          v-if="filedNotice"
          class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3"
        >
          <div>
            <p class="text-sm font-medium text-emerald-800">
              {{
                t('expense.invoices.filedNotice', { count: filedNotice.count })
              }}
            </p>
            <p class="mt-0.5 text-xs text-emerald-700">
              {{ t('expense.invoices.filedNoticeHint') }}
            </p>
          </div>
          <div class="flex gap-2">
            <BaseButton size="sm" variant="secondary" @click="undoFiling">
              {{ t('common.undo') }}
            </BaseButton>
            <BaseButton size="sm" @click="stage = 'filed'">
              {{ t('expense.invoices.goToFiled') }}
            </BaseButton>
          </div>
        </div>

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
          <div class="flex flex-wrap gap-2">
            <BaseButton
              size="sm"
              variant="secondary"
              @click="selectedUuids = []"
            >
              {{ t('expense.invoices.clearSelection') }}
            </BaseButton>
            <BaseButton
              v-if="stage === 'filed'"
              size="sm"
              :loading="filing"
              @click="restoreSelected"
            >
              {{ t('expense.invoices.restore') }}
            </BaseButton>
            <template v-else>
              <BaseButton
                size="sm"
                variant="secondary"
                :loading="filing"
                @click="fileOpen = true"
              >
                {{ t('expense.invoices.fileAway') }}
              </BaseButton>
              <BaseButton size="sm" @click="groupOpen = true">
                {{
                  stage === 'claiming'
                    ? t('expense.groups.moveAction')
                    : t('expense.groups.addAction')
                }}
              </BaseButton>
            </template>
          </div>
        </div>

        <InvoiceMonthList
          v-model="selectedUuids"
          :invoices="invoices"
          selectable
          @select="open"
        />
      </div>
    </BaseCard>
  </div>

  <FileAwayDialog
    v-if="fileOpen"
    :count="selectedUuids.length"
    :saving="filing"
    @close="fileOpen = false"
    @confirm="fileSelected"
  />

  <AddToGroupDialog
    v-if="groupOpen"
    :invoice-uuids="selectedUuids"
    :mode="stage === 'claiming' ? 'move' : 'add'"
    @close="groupOpen = false"
    @added="onGrouped"
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
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import AddToGroupDialog from '@/components/expense/AddToGroupDialog.vue'
import FileAwayDialog from '@/components/expense/FileAwayDialog.vue'
import FilterChips from '@/components/expense/FilterChips.vue'
import InvoiceDetailDrawer from '@/components/expense/InvoiceDetailDrawer.vue'
import InvoiceFilters from '@/components/expense/InvoiceFilters.vue'
import InvoiceMonthList from '@/components/expense/InvoiceMonthList.vue'
import { expenseApi } from '@/api/expense'

const emit = defineEmits(['rescanned', 'grouped'])

const { t } = useI18n()

const invoices = ref([])
const counts = ref({})
const buyers = ref([])
const stage = ref('todo')
const selectedUuids = ref([])
const groupOpen = ref(false)
const fileOpen = ref(false)
const filing = ref(false)
const filedNotice = ref(null)
const selected = ref(null)
const saving = ref(false)
const reextracting = ref(false)
const error = ref('')
const drawerError = ref('')
const filters = ref({
  q: '',
  buyer: '',
  category: '',
  needsReview: false
})

const stageOptions = computed(() => [
  { value: 'todo', label: t('expense.stages.todo'), count: counts.value.todo },
  {
    value: 'claiming',
    label: t('expense.stages.claiming'),
    count: counts.value.claiming
  },
  {
    value: 'reimbursed',
    label: t('expense.stages.reimbursed'),
    count: counts.value.reimbursed
  },
  {
    value: 'filed',
    label: t('expense.stages.filed'),
    count: counts.value.filed
  },
  { divider: true, value: '__divider__' },
  { value: 'all', label: t('expense.stages.all'), count: counts.value.all }
])

function readError(err, fallbackKey) {
  return err?.response?.data?.message || t(fallbackKey)
}

function queryParams() {
  const params = { stage: stage.value }
  if (filters.value.q) params.q = filters.value.q
  if (filters.value.buyer) params.buyer = filters.value.buyer
  if (filters.value.category) params.category = filters.value.category
  if (filters.value.needsReview) params.needs_review = 'true'
  return params
}

async function load() {
  error.value = ''
  try {
    const result = await expenseApi.getInvoices(queryParams())
    invoices.value = result.invoices || []
    counts.value = result.counts || {}
    buyers.value = result.buyers || []
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

async function fileSelected(reason) {
  const uuids = [...selectedUuids.value]
  filing.value = true
  error.value = ''
  try {
    const result = await expenseApi.fileAwayInvoices(uuids, reason)
    counts.value = result.counts || counts.value
    filedNotice.value = { count: result.filed, uuids }
    fileOpen.value = false
    selectedUuids.value = []
    await load()
  } catch (err) {
    error.value = readError(err, 'expense.invoices.fileFailed')
  } finally {
    filing.value = false
  }
}

async function undoFiling() {
  const uuids = filedNotice.value?.uuids || []
  filedNotice.value = null
  if (!uuids.length) return
  try {
    await expenseApi.restoreInvoices(uuids)
    await load()
  } catch (err) {
    error.value = readError(err, 'expense.invoices.fileFailed')
  }
}

async function restoreSelected() {
  filing.value = true
  error.value = ''
  try {
    await expenseApi.restoreInvoices([...selectedUuids.value])
    selectedUuids.value = []
    await load()
  } catch (err) {
    error.value = readError(err, 'expense.invoices.fileFailed')
  } finally {
    filing.value = false
  }
}

async function onGrouped() {
  groupOpen.value = false
  selectedUuids.value = []
  await load()
  // The group totals changed, so whoever owns that list needs to know.
  emit('grouped')
}

// A selection made under one filter means nothing under the next.
watch(stage, () => {
  selectedUuids.value = []
  filedNotice.value = null
  load()
})
watch(filters, load, { deep: true })
onMounted(load)

defineExpose({ load })
</script>
