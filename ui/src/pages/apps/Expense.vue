<template>
  <AppLayout>
    <div class="space-y-6">
      <div>
        <h1 class="text-2xl font-semibold text-gray-900">
          {{ t('expense.pageTitle') }}
        </h1>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('expense.pageSubtitle') }}
        </p>
      </div>

      <BaseCard v-if="loading">
        <div class="space-y-4 animate-pulse">
          <div class="h-5 w-40 rounded bg-gray-200"></div>
          <div class="h-20 rounded bg-gray-100"></div>
        </div>
      </BaseCard>

      <template v-else>
        <p
          v-if="error"
          class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {{ error }}
        </p>

        <ExpenseEnableCard
          v-if="config"
          :model-value="config"
          :saving="saving"
          @toggle="handleToggle"
        />

        <ScanRunList
          v-if="config?.enabled"
          :runs="runs"
          :scanning="scanning"
          @scan="openPreview"
        />
      </template>

      <ScanPreviewDialog
        v-if="previewOpen"
        :preview="preview"
        :loading="previewLoading"
        :error="previewError"
        @close="previewOpen = false"
        @confirm="confirmScan"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import ExpenseEnableCard from '@/components/expense/ExpenseEnableCard.vue'
import ScanPreviewDialog from '@/components/expense/ScanPreviewDialog.vue'
import ScanRunList from '@/components/expense/ScanRunList.vue'
import { expenseApi } from '@/api/expense'

const { t } = useI18n()

const config = ref(null)
const runs = ref([])
const loading = ref(true)
const saving = ref(false)
const scanning = ref(false)
const error = ref('')

const previewOpen = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const preview = ref(null)

function readError(err, fallbackKey) {
  return err?.response?.data?.message || t(fallbackKey)
}

async function loadRuns() {
  if (!config.value?.enabled) {
    runs.value = []
    return
  }
  try {
    runs.value = await expenseApi.getScanRuns()
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

async function loadConfig() {
  loading.value = true
  error.value = ''
  try {
    config.value = await expenseApi.getConfig()
    await loadRuns()
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  } finally {
    loading.value = false
  }
}

async function handleToggle(enabled) {
  saving.value = true
  error.value = ''
  try {
    config.value = await expenseApi.updateConfig({ enabled })
    await loadRuns()
  } catch (err) {
    error.value = readError(err, 'expense.saveFailed')
  } finally {
    saving.value = false
  }
}

// The cost is always shown before a scan starts, never after.
async function openPreview() {
  previewOpen.value = true
  previewLoading.value = true
  previewError.value = ''
  preview.value = null
  try {
    preview.value = await expenseApi.previewScan({})
  } catch (err) {
    previewError.value = readError(err, 'expense.scan.previewFailed')
  } finally {
    previewLoading.value = false
  }
}

async function confirmScan() {
  scanning.value = true
  previewOpen.value = false
  error.value = ''
  try {
    await expenseApi.startScan({})
    await loadRuns()
  } catch (err) {
    error.value = readError(err, 'expense.scan.startFailed')
  } finally {
    scanning.value = false
  }
}

onMounted(loadConfig)
</script>
