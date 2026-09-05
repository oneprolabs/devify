<template>
  <div class="flex flex-col">
    <!-- The canvas runs these bands edge to edge, separated by hairlines,
         rather than boxing the list in a card. -->
    <div class="flex-shrink-0 px-4 pt-3.5 md:px-5">
      <FilterChips v-model="stage" :options="stageOptions" />
    </div>

    <div class="flex flex-col">
      <div
        class="flex flex-col gap-3.5 border-b border-line px-4 pb-4 pt-3.5 md:px-5"
      >
        <InvoiceFilters v-model="filters" :buyers="buyers" />

        <p
          v-if="error"
          class="rounded-lg border border-bad bg-bad-soft p-3 text-sm text-bad"
        >
          {{ error }}
        </p>

        <!-- Filing something away is silent by nature: the row simply
             leaves the list. This says where it went and offers the way
             back, so the action never feels like a deletion. -->
        <div
          v-if="filedNotice"
          class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-ok bg-ok-soft p-3"
        >
          <div>
            <p class="text-sm font-medium text-ok">
              {{
                t('expense.invoices.filedNotice', { count: filedNotice.count })
              }}
            </p>
            <p class="mt-0.5 text-xs text-ok">
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
      </div>

      <div
        v-if="selectedUuids.length"
        class="mx-4 mt-3.5 flex flex-wrap items-center justify-between gap-3 rounded-md border border-accent bg-accent-soft px-3.5 py-2.5 md:mx-5"
      >
        <span class="text-sm text-accent">
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

      <div class="pt-3">
        <InvoiceMonthList
          v-model="selectedUuids"
          :invoices="invoices"
          selectable
          @select="open"
        />
      </div>
    </div>
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
