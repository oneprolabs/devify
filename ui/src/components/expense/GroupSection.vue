<template>
  <!-- The artboard lays this out as a workbench, not a list: a 300px rail
       of batches on the left and one batch in full on the right. A batch is
       something you work through invoice by invoice, and the old shape made
       you expand a row to see any of it. -->
  <div class="flex min-h-0 flex-1">
    <div
      class="flex flex-col border-line md:w-[300px] md:flex-none md:border-r"
      :class="selected && !isWide ? 'hidden' : 'w-full'"
    >
      <div
        class="flex h-12 flex-none items-center gap-2 border-b border-line px-3.5"
      >
        <FilterSelect
          v-model="filter"
          :label="filterLabel"
          :options="filterOptions"
          size="sm"
        />
        <button
          type="button"
          class="ml-auto flex h-[30px] flex-none items-center gap-1.5 rounded-md bg-accent px-3 text-[calc(12px*var(--fs))] font-medium text-accent-on"
          @click="startNaming"
        >
          <svg
            class="h-[13px] w-[13px]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            aria-hidden="true"
          >
            <path d="M12 5v14M5 12h14" stroke-linecap="round" />
          </svg>
          {{ t('expense.groups.create') }}
        </button>
      </div>

      <div v-if="naming" class="flex-none border-b border-line p-3.5">
        <input
          ref="nameInput"
          v-model="newName"
          type="text"
          class="h-[30px] w-full rounded-md border border-line bg-panel px-[11px] text-[calc(12px*var(--fs))] text-ink focus:border-accent focus:outline-none focus:ring-0"
          :placeholder="t('expense.groups.namePlaceholder')"
          @keyup.enter="create"
          @keyup.esc="naming = false"
        />
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto">
        <p
          v-if="!visible.length"
          class="px-3.5 py-6 text-center text-[calc(12px*var(--fs))] text-ink-3"
        >
          {{ t('expense.groups.empty') }}
        </p>

        <button
          v-for="group in visible"
          :key="group.uuid"
          type="button"
          class="flex w-full flex-col gap-[5px] border-b border-line-soft border-l-2 px-3.5 py-3 text-left"
          :class="
            selected?.uuid === group.uuid
              ? 'border-l-accent bg-accent-soft'
              : 'border-l-transparent hover:bg-chip'
          "
          @click="open(group)"
        >
          <div class="flex min-w-0 items-center gap-[7px]">
            <span
              class="truncate text-[calc(13px*var(--fs))] font-medium text-ink"
            >
              {{ group.name }}
            </span>
            <span
              v-if="group.trip_type === 'business_trip'"
              class="font-mono flex-none rounded-sm border border-accent px-[5px] py-px text-[calc(9.5px*var(--fs))] text-accent"
            >
              {{ t('expense.groups.businessTrip') }}
            </span>
            <span
              class="font-mono ml-auto flex-none rounded-sm bg-panel-sub px-1.5 py-0.5 text-[calc(9.5px*var(--fs))]"
              :class="group.status === 'draft' ? 'text-warn' : 'text-ink-3'"
            >
              {{ t(`expense.groups.statuses.${group.status}`) }}
            </span>
          </div>
          <span class="font-mono text-[calc(11px*var(--fs))] text-ink-3">
            {{
              t('expense.groups.line', {
                count: group.invoice_count,
                amount: formatAmount(group.total_amount)
              })
            }}
          </span>
        </button>
      </div>
    </div>

    <GroupDetailPanel
      v-if="selected && summary"
      :group="selected"
      :summary="summary"
      :sections="sections"
      :removing="removing"
      :exporting="exporting === selected.uuid"
      :settling="settling"
      :error="detailError"
      :can-go-back="!isWide"
      @back="selected = null"
      @remove="removeInvoice"
      @move="startMove"
      @export="exportGroup"
      @settle="markReimbursed"
    />

    <div
      v-else-if="isWide"
      class="flex flex-1 items-center justify-center text-[calc(12px*var(--fs))] text-ink-3"
    >
      {{ error || t('expense.groups.pickOne') }}
    </div>
  </div>

  <AddToGroupDialog
    v-if="moving"
    :invoice-uuids="[moving.uuid]"
    mode="move"
    @close="moving = null"
    @added="onMoved"
  />
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import FilterSelect from '@/components/ui/FilterSelect.vue'
import AddToGroupDialog from '@/components/expense/AddToGroupDialog.vue'
import GroupDetailPanel from '@/components/expense/GroupDetailPanel.vue'
import { expenseApi } from '@/api/expense'
import { formatAmount } from '@/utils/formatting'
import apiConfig from '@/config/api'

const { t } = useI18n()

const groups = ref([])
const filter = ref('live')
const summary = ref(null)
const sections = ref([])
const selected = ref(null)
const moving = ref(null)
const removing = ref('')
const newName = ref('')
const creating = ref(false)
const exporting = ref('')
const error = ref('')
const detailError = ref('')
const settling = ref(false)

// The rail and a batch cannot share 390px, so a phone shows the list and
// then the batch, the way the artboard splits them into two screens.
const WIDE = window.matchMedia('(min-width: 768px)')
const isWide = ref(WIDE.matches)
const syncWide = (event) => {
  isWide.value = event.matches
}
onMounted(() => WIDE.addEventListener('change', syncWide))
onBeforeUnmount(() => WIDE.removeEventListener('change', syncWide))
const naming = ref(false)
const nameInput = ref(null)

const LIVE_STATES = ['draft', 'submitted']

const visible = computed(() => {
  if (filter.value === 'live') {
    return groups.value.filter((group) => LIVE_STATES.includes(group.status))
  }
  if (filter.value === 'reimbursed') {
    return groups.value.filter((group) => group.status === 'reimbursed')
  }
  return groups.value
})

const filterOptions = computed(() => [
  { value: 'live', label: t('expense.groups.filters.live') },
  { value: 'reimbursed', label: t('expense.groups.filters.reimbursed') },
  { value: 'all', label: t('expense.groups.filters.all') }
])

const filterLabel = computed(
  () =>
    filterOptions.value.find((option) => option.value === filter.value)
      ?.label || t('expense.groups.filters.live')
)

function readError(err, fallbackKey) {
  return err?.response?.data?.message || t(fallbackKey)
}

async function load() {
  try {
    groups.value = await expenseApi.getGroups()
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

// The field appears on demand, so it has to take the caret with it —
// otherwise the button opens an input the reader then has to click.
async function startNaming() {
  naming.value = true
  await nextTick()
  nameInput.value?.focus()
}

async function create() {
  const name = newName.value.trim()
  if (!name) return
  creating.value = true
  error.value = ''
  try {
    const created = await expenseApi.createGroup({ name })
    newName.value = ''
    naming.value = false
    await load()
    if (created?.uuid) await loadDetail(created.uuid)
  } catch (err) {
    error.value = readError(err, 'expense.groups.createFailed')
  } finally {
    creating.value = false
  }
}

async function loadDetail(uuid) {
  const [summaryData, detailData] = await Promise.all([
    expenseApi.getGroupSummary(uuid),
    expenseApi.getGroup(uuid)
  ])
  summary.value = summaryData
  sections.value = detailData.sections || []
  selected.value = detailData
}

async function open(group) {
  if (selected.value?.uuid === group.uuid) return
  error.value = ''
  detailError.value = ''
  try {
    await loadDetail(group.uuid)
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

async function removeInvoice(invoice) {
  removing.value = invoice.uuid
  detailError.value = ''
  try {
    await expenseApi.removeGroupItems(selected.value.uuid, [invoice.uuid])
    // Totals and membership both moved, so reload the group and the list.
    await loadDetail(selected.value.uuid)
    await load()
  } catch (err) {
    detailError.value = readError(err, 'expense.groups.createFailed')
  } finally {
    removing.value = ''
  }
}

// Marking a batch reimbursed is the last thing that happens to it, and the
// artboard puts it beside the export rather than in a menu.
async function markReimbursed(group) {
  settling.value = true
  detailError.value = ''
  try {
    await expenseApi.updateGroup(group.uuid, { status: 'reimbursed' })
    await loadDetail(group.uuid)
    await load()
  } catch (err) {
    detailError.value = readError(err, 'expense.groups.createFailed')
  } finally {
    settling.value = false
  }
}

function startMove(invoice) {
  moving.value = invoice
}

async function onMoved() {
  moving.value = null
  detailError.value = ''
  try {
    await loadDetail(selected.value.uuid)
    await load()
  } catch (err) {
    detailError.value = readError(err, 'expense.loadFailed')
  }
}

// The archive is a real download, so it goes through the browser rather
// than being buffered in JavaScript.
function exportGroup(group) {
  exporting.value = group.uuid
  const url = `${apiConfig.apiBaseUrl}/v1/apps/expense/groups/${group.uuid}/export`
  window.open(url, '_blank', 'noopener')
  setTimeout(() => {
    exporting.value = ''
    load()
  }, 1500)
}

// The right-hand side needs something in it, and the first live batch is
// what the reader came for.
onMounted(async () => {
  await load()
  const first = visible.value[0]
  if (first && isWide.value) await open(first)
})
defineExpose({ load })
</script>
