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

      <p
        v-else-if="error"
        class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
      >
        {{ error }}
      </p>

      <ExpenseEnableCard
        v-else-if="config"
        :model-value="config"
        :saving="saving"
        @toggle="handleToggle"
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
import { expenseApi } from '@/api/expense'

const { t } = useI18n()

const config = ref(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')

async function loadConfig() {
  loading.value = true
  error.value = ''
  try {
    config.value = await expenseApi.getConfig()
  } catch (err) {
    error.value = err?.response?.data?.message || t('expense.loadFailed')
  } finally {
    loading.value = false
  }
}

async function handleToggle(enabled) {
  saving.value = true
  error.value = ''
  try {
    config.value = await expenseApi.updateConfig({ enabled })
  } catch (err) {
    error.value = err?.response?.data?.message || t('expense.saveFailed')
  } finally {
    saving.value = false
  }
}

onMounted(loadConfig)
</script>
