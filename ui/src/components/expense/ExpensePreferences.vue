<template>
  <!-- The artboard sets each setting out as a row: what it is and what it
       affects on the left, the control on the right. A phone has no room
       for two columns, so there the label and its explanation sit above
       the control instead. -->
  <!-- flex-none: this sits in a flex column, and without it the card
       is squeezed down to its header. -->
  <div class="flex-none overflow-hidden rounded-[9px] border border-line">
    <div class="border-b border-line bg-panel-sub px-4 py-3">
      <h2 class="text-[calc(13px*var(--fs))] font-semibold text-ink">
        {{ t('expense.prefs.title') }}
      </h2>
      <p class="mt-0.5 text-[calc(11.5px*var(--fs))] text-ink-3">
        {{ t('expense.prefs.subtitle') }}
      </p>
    </div>

    <p
      v-if="error"
      class="border-b border-line-soft bg-bad-soft px-4 py-3 text-[calc(12px*var(--fs))] text-bad"
    >
      {{ error }}
    </p>
    <p
      v-else-if="saved"
      class="border-b border-line-soft bg-ok-soft px-4 py-3 text-[calc(12px*var(--fs))] text-ok"
    >
      {{ t('expense.prefs.saved') }}
    </p>

    <div
      v-for="row in rows"
      :key="row.key"
      class="grid gap-2 border-b border-line-soft px-4 py-3.5 md:grid-cols-[240px_minmax(0,1fr)] md:gap-6"
    >
      <div class="flex flex-col gap-1">
        <span class="text-[calc(12.5px*var(--fs))] font-medium text-ink">
          {{ t(`expense.prefs.${row.key}`) }}
        </span>
        <span class="text-[calc(11px*var(--fs))] leading-[1.6] text-ink-3">
          {{ t(`expense.prefs.${row.key}Help`) }}
        </span>
      </div>

      <div class="flex min-w-0 flex-col gap-1.5">
        <input
          v-if="row.key === 'homeCity'"
          v-model="form.home_city"
          type="text"
          class="w-full rounded-md border border-line bg-panel px-[11px] py-2 text-[calc(12.5px*var(--fs))] text-ink focus:border-accent focus:outline-none focus:ring-0"
          :placeholder="t('expense.prefs.homeCityPlaceholder')"
        />

        <template v-else-if="row.key === 'filenameTemplate'">
          <div
            class="flex items-center justify-between gap-3 rounded-md border border-line px-[11px] py-2"
          >
            <span
              class="font-mono truncate text-[calc(11.5px*var(--fs))] text-ink-2"
              :title="namingSample"
            >
              {{ namingSample || t('expense.prefs.filenameLoading') }}
            </span>
            <BaseButton size="sm" variant="outline" @click="namingOpen = true">
              {{ t('common.edit') }}
            </BaseButton>
          </div>
        </template>

        <textarea
          v-else-if="row.key === 'keywords'"
          v-model="keywordsText"
          class="w-full rounded-md border border-line bg-panel px-[11px] py-2 text-[calc(12.5px*var(--fs))] text-ink focus:border-accent focus:outline-none focus:ring-0"
          rows="3"
          :placeholder="t('expense.prefs.keywordsPlaceholder')"
        />

        <textarea
          v-else
          v-model="sendersText"
          class="w-full rounded-md border border-line bg-panel px-[11px] py-2 text-[calc(12.5px*var(--fs))] text-ink focus:border-accent focus:outline-none focus:ring-0"
          rows="3"
          :placeholder="t('expense.prefs.sendersPlaceholder')"
        />

        <span
          v-if="row.key === 'keywords'"
          class="rounded-md bg-panel-sub p-2 text-[calc(11px*var(--fs))] leading-[1.7] text-ink-3"
        >
          {{ t('expense.prefs.keywordsScope') }}
        </span>
      </div>
    </div>

    <div class="flex justify-end px-4 py-3">
      <BaseButton :loading="saving" @click="save">
        {{ t('common.save') }}
      </BaseButton>
    </div>
  </div>

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

// One row per setting, in the artboard's order.
const rows = [
  { key: 'homeCity' },
  { key: 'filenameTemplate' },
  { key: 'keywords' },
  { key: 'senders' }
]

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
