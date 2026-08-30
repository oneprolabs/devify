<template>
  <BaseCard>
    <div class="space-y-5">
      <div>
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('expense.prefs.title') }}
        </h2>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('expense.prefs.subtitle') }}
        </p>
      </div>

      <p
        v-if="error"
        class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        {{ error }}
      </p>
      <p
        v-else-if="saved"
        class="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800"
      >
        {{ t('expense.prefs.saved') }}
      </p>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">
            {{ t('expense.prefs.homeCity') }}
          </span>
          <input
            v-model="form.home_city"
            type="text"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            :placeholder="t('expense.prefs.homeCityPlaceholder')"
          />
          <span class="mt-1 block text-xs text-gray-500">
            {{ t('expense.prefs.homeCityHelp') }}
          </span>
        </label>

        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">
            {{ t('expense.prefs.filenameTemplate') }}
          </span>
          <input
            v-model="form.filename_template"
            type="text"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-xs focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            :placeholder="defaultTemplate"
          />
          <span class="mt-1 block text-xs text-gray-500">
            {{ t('expense.prefs.filenameTemplateHelp') }}
          </span>
        </label>
      </div>

      <label class="block">
        <span class="mb-1 block text-sm font-medium text-gray-700">
          {{ t('expense.prefs.keywords') }}
        </span>
        <textarea
          v-model="keywordsText"
          class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          rows="3"
          :placeholder="t('expense.prefs.keywordsPlaceholder')"
        />
        <span class="mt-1 block text-xs text-gray-500">
          {{ t('expense.prefs.keywordsHelp') }}
        </span>
      </label>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">
            {{ t('expense.prefs.senders') }}
          </span>
          <textarea
            v-model="sendersText"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            rows="3"
            :placeholder="t('expense.prefs.sendersPlaceholder')"
          />
          <span class="mt-1 block text-xs text-gray-500">
            {{ t('expense.prefs.sendersHelp') }}
          </span>
        </label>

        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">
            {{ t('expense.prefs.linkDomains') }}
          </span>
          <textarea
            v-model="domainsText"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            rows="3"
            :placeholder="t('expense.prefs.linkDomainsPlaceholder')"
          />
          <span class="mt-1 block text-xs text-gray-500">
            {{ t('expense.prefs.linkDomainsHelp') }}
          </span>
        </label>
      </div>

      <div class="flex justify-end">
        <BaseButton :loading="saving" @click="save">
          {{ t('common.save') }}
        </BaseButton>
      </div>
    </div>
  </BaseCard>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import { expenseApi } from '@/api/expense'

const props = defineProps({
  config: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['updated'])

const { t } = useI18n()

const defaultTemplate = '{issue_date}_{category}_{seller}_{amount}_{invoice_no}'

const form = reactive({ home_city: '', filename_template: '' })
const keywordsText = ref('')
const sendersText = ref('')
const domainsText = ref('')
const saving = ref(false)
const saved = ref(false)
const error = ref('')

function toText(list) {
  return Array.isArray(list) ? list.join('\n') : ''
}

function toList(text) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function load(config) {
  form.home_city = config.home_city || ''
  form.filename_template = config.filename_template || ''
  keywordsText.value = toText(config.keyword_filters)
  sendersText.value = toText(config.sender_allowlist)
  domainsText.value = toText(config.extra_link_domains)
}

watch(() => props.config, load, { immediate: true })

async function save() {
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    const updated = await expenseApi.updateConfig({
      home_city: form.home_city,
      filename_template: form.filename_template,
      keyword_filters: toList(keywordsText.value),
      sender_allowlist: toList(sendersText.value),
      extra_link_domains: toList(domainsText.value)
    })
    saved.value = true
    emit('updated', updated)
  } catch (err) {
    error.value = err?.response?.data?.message || t('expense.saveFailed')
  } finally {
    saving.value = false
  }
}
</script>
