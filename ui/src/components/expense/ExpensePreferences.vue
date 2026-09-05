<template>
  <BaseCard>
    <div class="space-y-5">
      <div>
        <h2 class="text-lg font-semibold text-ink">
          {{ t('expense.prefs.title') }}
        </h2>
        <p class="mt-1 text-sm text-ink-3">
          {{ t('expense.prefs.subtitle') }}
        </p>
      </div>

      <p
        v-if="error"
        class="rounded-lg border border-bad bg-bad-soft p-3 text-sm text-bad"
      >
        {{ error }}
      </p>
      <p
        v-else-if="saved"
        class="rounded-lg border border-ok bg-ok-soft p-3 text-sm text-ok"
      >
        {{ t('expense.prefs.saved') }}
      </p>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('expense.prefs.homeCity') }}
          </span>
          <input
            v-model="form.home_city"
            type="text"
            class="w-full rounded-lg border border-line px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            :placeholder="t('expense.prefs.homeCityPlaceholder')"
          />
          <span class="mt-1 block text-xs text-ink-3">
            {{ t('expense.prefs.homeCityHelp') }}
          </span>
        </label>

        <div class="block">
          <span class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('expense.prefs.filenameTemplate') }}
          </span>
          <div
            class="flex items-center justify-between gap-3 rounded-lg border border-line px-3 py-2"
          >
            <span
              class="truncate font-mono text-xs text-ink-2"
              :title="namingSample"
            >
              {{ namingSample || t('expense.prefs.filenameLoading') }}
            </span>
            <BaseButton size="sm" variant="outline" @click="namingOpen = true">
              {{ t('common.edit') }}
            </BaseButton>
          </div>
          <span class="mt-1 block text-xs text-ink-3">
            {{ t('expense.prefs.filenameTemplateHelp') }}
          </span>
        </div>
      </div>

      <label class="block">
        <span class="mb-1 block text-sm font-medium text-ink-2">
          {{ t('expense.prefs.keywords') }}
        </span>
        <textarea
          v-model="keywordsText"
          class="w-full rounded-lg border border-line px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          rows="3"
          :placeholder="t('expense.prefs.keywordsPlaceholder')"
        />
        <span class="mt-1 block text-xs text-ink-3">
          {{ t('expense.prefs.keywordsHelp') }}
        </span>
        <span
          class="mt-2 block rounded-md bg-app-sub p-2 text-xs leading-relaxed text-ink-3"
        >
          {{ t('expense.prefs.keywordsScope') }}
        </span>
      </label>

      <div>
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('expense.prefs.senders') }}
          </span>
          <textarea
            v-model="sendersText"
            class="w-full rounded-lg border border-line px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            rows="3"
            :placeholder="t('expense.prefs.sendersPlaceholder')"
          />
          <span class="mt-1 block text-xs text-ink-3">
            {{ t('expense.prefs.sendersHelp') }}
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

  <FilenameTemplateDialog
    v-if="namingOpen"
    @close="namingOpen = false"
    @saved="loadNamingSample"
  />
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import FilenameTemplateDialog from '@/components/expense/FilenameTemplateDialog.vue'
import { expenseApi } from '@/api/expense'

const props = defineProps({
  config: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['updated'])

const { t } = useI18n()

const form = reactive({ home_city: '' })
const namingOpen = ref(false)
const namingSample = ref('')
const keywordsText = ref('')
const sendersText = ref('')
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
  keywordsText.value = toText(config.keyword_filters)
  sendersText.value = toText(config.sender_allowlist)
}

// The name is easier to judge from an example than from a template
// string, so the field shows what the current layout produces.
async function loadNamingSample() {
  try {
    const data = await expenseApi.getNaming()
    namingSample.value = (data.preview || [])[0] || ''
  } catch {
    namingSample.value = ''
  }
}

watch(() => props.config, load, { immediate: true })
onMounted(loadNamingSample)

async function save() {
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    const updated = await expenseApi.updateConfig({
      home_city: form.home_city,
      keyword_filters: toList(keywordsText.value),
      sender_allowlist: toList(sendersText.value)
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
