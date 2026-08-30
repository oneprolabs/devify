<template>
  <BaseCard>
    <div class="space-y-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('expense.groups.title') }}
          </h2>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('expense.groups.subtitle') }}
          </p>
        </div>

        <div class="flex gap-2">
          <input
            v-model="newName"
            type="text"
            class="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            :placeholder="t('expense.groups.namePlaceholder')"
            @keyup.enter="create"
          />
          <BaseButton size="sm" :loading="creating" @click="create">
            {{ t('expense.groups.create') }}
          </BaseButton>
        </div>
      </div>

      <p
        v-if="error"
        class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        {{ error }}
      </p>

      <p v-if="!groups.length" class="py-6 text-center text-sm text-gray-500">
        {{ t('expense.groups.empty') }}
      </p>

      <ul v-else class="divide-y divide-gray-100">
        <li
          v-for="group in groups"
          :key="group.uuid"
          class="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <button type="button" class="min-w-0 text-left" @click="open(group)">
            <p class="truncate text-sm font-medium text-gray-900">
              {{ group.name }}
            </p>
            <p class="mt-0.5 text-xs text-gray-500">
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
              {{ t('expense.groups.viewSummary') }}
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
    </div>
  </BaseCard>

  <BaseModal :show="!!summary" @close="summary = null">
    <div v-if="summary" class="space-y-4">
      <h3 class="text-lg font-semibold text-gray-900">
        {{ selectedName }}
      </h3>
      <GroupSummaryPanel :summary="summary" />
    </div>
  </BaseModal>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import GroupSummaryPanel from '@/components/expense/GroupSummaryPanel.vue'
import { expenseApi } from '@/api/expense'
import apiConfig from '@/config/api'

const { t } = useI18n()

const groups = ref([])
const summary = ref(null)
const selected = ref(null)
const newName = ref('')
const creating = ref(false)
const exporting = ref('')
const error = ref('')

const selectedName = computed(() => selected.value?.name || '')

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

async function open(group) {
  error.value = ''
  selected.value = group
  try {
    summary.value = await expenseApi.getGroupSummary(group.uuid)
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
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
