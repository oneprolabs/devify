<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-ink">
          {{ t('expense.groups.title') }}
        </h2>
        <p class="mt-1 text-sm text-ink-3">
          {{ t('expense.groups.subtitle') }}
        </p>
      </div>

      <div class="flex gap-2">
        <input
          v-model="newName"
          type="text"
          class="rounded-lg border border-line px-3 py-2 text-sm focus:border-accent focus:outline-none"
          :placeholder="t('expense.groups.namePlaceholder')"
          @keyup.enter="create"
        />
        <BaseButton size="sm" :loading="creating" @click="create">
          {{ t('expense.groups.create') }}
        </BaseButton>
      </div>
    </div>

    <FilterChips v-model="filter" :options="filterOptions" />

    <p
      v-if="error"
      class="rounded-lg border border-bad bg-bad-soft p-3 text-sm text-bad"
    >
      {{ error }}
    </p>

    <BaseCard>
      <p v-if="!visible.length" class="py-6 text-center text-sm text-ink-3">
        {{ t('expense.groups.empty') }}
      </p>

      <ul v-else class="divide-y divide-line-soft">
        <li
          v-for="group in visible"
          :key="group.uuid"
          class="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <button type="button" class="min-w-0 text-left" @click="open(group)">
            <p class="truncate text-sm font-medium text-ink">
              {{ group.name }}
              <span
                v-if="group.status !== 'draft'"
                class="ml-1 rounded-full bg-chip px-2 py-0.5 text-[calc(11px*var(--fs))] text-ink-2"
              >
                {{ t(`expense.groups.statuses.${group.status}`) }}
              </span>
            </p>
            <p class="mt-0.5 text-xs text-ink-3">
              {{
                t('expense.groups.line', {
                  count: group.invoice_count,
                  amount: group.total_amount
                })
              }}
              <span v-if="group.trip_type === 'business_trip'">
                · {{ t('expense.groups.businessTrip') }}
              </span>
            </p>
          </button>

          <div class="flex gap-2">
            <BaseButton size="sm" variant="outline" @click="open(group)">
              {{
                selected?.uuid === group.uuid
                  ? t('common.collapse')
                  : t('common.expand')
              }}
            </BaseButton>
            <BaseButton
              size="sm"
              variant="outline"
              :loading="exporting === group.uuid"
              @click="exportGroup(group)"
            >
              {{ t('expense.groups.export') }}
            </BaseButton>
          </div>
        </li>
      </ul>
    </BaseCard>

    <GroupDetailPanel
      v-if="selected && summary"
      :group="selected"
      :summary="summary"
      :sections="sections"
      :removing="removing"
      :exporting="exporting === selected.uuid"
      :error="detailError"
      @close="close"
      @remove="removeInvoice"
      @move="startMove"
      @export="exportGroup"
    />
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
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import AddToGroupDialog from '@/components/expense/AddToGroupDialog.vue'
import FilterChips from '@/components/expense/FilterChips.vue'
import GroupDetailPanel from '@/components/expense/GroupDetailPanel.vue'
import { expenseApi } from '@/api/expense'
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
  {
    value: 'live',
    label: t('expense.groups.filters.live'),
    count: groups.value.filter((group) => LIVE_STATES.includes(group.status))
      .length
  },
  {
    value: 'reimbursed',
    label: t('expense.groups.filters.reimbursed'),
    count: groups.value.filter((group) => group.status === 'reimbursed').length
  },
  {
    value: 'all',
    label: t('expense.groups.filters.all'),
    count: groups.value.length
  }
])

function close() {
  selected.value = null
  summary.value = null
  sections.value = []
}

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

async function create() {
  const name = newName.value.trim()
  if (!name) return
  creating.value = true
  error.value = ''
  try {
    await expenseApi.createGroup({ name })
    newName.value = ''
    await load()
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
  if (selected.value?.uuid === group.uuid) {
    close()
    return
  }
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

onMounted(load)
defineExpose({ load })
</script>
