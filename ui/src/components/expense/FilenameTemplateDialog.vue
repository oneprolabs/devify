<template>
  <BaseModal :show="true" @close="$emit('close')">
    <div class="space-y-5">
      <div>
        <h3 class="text-lg font-semibold text-gray-900">
          {{ t('expense.naming.title') }}
        </h3>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('expense.naming.subtitle') }}
        </p>
      </div>

      <p
        v-if="error"
        class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        {{ error }}
      </p>

      <div class="rounded-lg border border-primary-200 bg-primary-50 p-4">
        <p class="text-sm font-medium text-primary-900">
          {{ t('expense.naming.previewTitle') }}
        </p>
        <ul class="mt-2 space-y-1">
          <li
            v-for="(name, i) in preview"
            :key="i"
            class="truncate font-mono text-xs text-primary-800"
            :title="name"
          >
            {{ name }}
          </li>
        </ul>
      </div>

      <ul class="divide-y divide-gray-100 rounded-lg border border-gray-200">
        <li
          v-for="(field, i) in ordered"
          :key="field.key"
          class="flex items-center gap-3 px-3 py-2.5"
          :class="dragIndex === i ? 'bg-gray-50' : ''"
          draggable="true"
          @dragstart="dragIndex = i"
          @dragover.prevent
          @drop="drop(i)"
          @dragend="dragIndex = null"
        >
          <input
            type="checkbox"
            class="rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-40"
            :checked="selected.includes(field.key)"
            :disabled="field.required"
            :title="field.required ? t('expense.naming.alwaysOn') : ''"
            @change="toggle(field.key, $event.target.checked)"
          />

          <span class="flex-1 text-sm text-gray-900">
            {{ t(`expense.naming.fields.${field.key}`) }}
            <span v-if="field.required" class="ml-1 text-xs text-gray-400">
              {{ t('expense.naming.required') }}
            </span>
          </span>

          <div class="flex items-center gap-1">
            <button
              type="button"
              class="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-30"
              :disabled="i === 0"
              :aria-label="t('expense.naming.moveUp')"
              @click="move(i, -1)"
            >
              ↑
            </button>
            <button
              type="button"
              class="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-30"
              :disabled="i === ordered.length - 1"
              :aria-label="t('expense.naming.moveDown')"
              @click="move(i, 1)"
            >
              ↓
            </button>
          </div>
        </li>
      </ul>

      <div class="flex items-center justify-between gap-3">
        <button
          type="button"
          class="text-xs text-gray-500 hover:text-gray-700 hover:underline"
          @click="restoreDefault"
        >
          {{ t('expense.naming.restoreDefault') }}
        </button>

        <div class="flex gap-3">
          <BaseButton variant="secondary" @click="$emit('close')">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton :loading="saving" @click="save">
            {{ t('common.save') }}
          </BaseButton>
        </div>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { expenseApi } from '@/api/expense'

const emit = defineEmits(['close', 'saved'])

const { t } = useI18n()

const available = ref([])
const selected = ref([])
const order = ref([])
const preview = ref([])
const defaultTemplate = ref('')
const saving = ref(false)
const error = ref('')
const dragIndex = ref(null)

// Chosen fields first, in the order they appear in the name; the rest sit
// below so adding one does not mean hunting for it.
const ordered = computed(() => {
  const byKey = new Map(available.value.map((f) => [f.key, f]))
  const chosen = order.value.map((key) => byKey.get(key)).filter(Boolean)
  const rest = available.value.filter((f) => !order.value.includes(f.key))
  return [...chosen, ...rest]
})

function readError(err, fallbackKey) {
  return err?.response?.data?.message || t(fallbackKey)
}

async function load() {
  try {
    const data = await expenseApi.getNaming()
    available.value = data.available_fields || []
    selected.value = data.selected_fields || []
    order.value = [...selected.value]
    preview.value = data.preview || []
    defaultTemplate.value = data.default_template || ''
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

async function refreshPreview() {
  try {
    const data = await expenseApi.previewNaming(order.value)
    preview.value = data.preview || []
  } catch (err) {
    error.value = readError(err, 'expense.loadFailed')
  }
}

function toggle(key, checked) {
  if (checked) {
    if (!order.value.includes(key)) order.value.push(key)
  } else {
    order.value = order.value.filter((item) => item !== key)
  }
  selected.value = [...order.value]
  refreshPreview()
}

function move(index, delta) {
  const list = ordered.value
    .map((f) => f.key)
    .filter((k) => order.value.includes(k))
  const from = list.indexOf(ordered.value[index].key)
  if (from < 0) return
  const to = from + delta
  if (to < 0 || to >= list.length) return
  list.splice(to, 0, list.splice(from, 1)[0])
  order.value = list
  refreshPreview()
}

function drop(index) {
  if (dragIndex.value === null || dragIndex.value === index) return
  const fromKey = ordered.value[dragIndex.value].key
  const toKey = ordered.value[index].key
  if (!order.value.includes(fromKey) || !order.value.includes(toKey)) return
  const list = [...order.value]
  list.splice(list.indexOf(toKey), 0, list.splice(list.indexOf(fromKey), 1)[0])
  order.value = list
  dragIndex.value = null
  refreshPreview()
}

async function restoreDefault() {
  try {
    await expenseApi.updateConfig({ filename_template: '' })
    await load()
    emit('saved')
  } catch (err) {
    error.value = readError(err, 'expense.saveFailed')
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const data = await expenseApi.previewNaming(order.value)
    await expenseApi.updateConfig({ filename_template: data.template })
    emit('saved')
    emit('close')
  } catch (err) {
    error.value = readError(err, 'expense.saveFailed')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
