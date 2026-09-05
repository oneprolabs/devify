<template>
  <div class="flex min-w-0 flex-1 items-center gap-3">
    <label
      class="flex h-8 max-w-[442px] flex-1 items-center gap-2 rounded-md border border-line bg-panel-sub px-2.5"
    >
      <svg
        class="h-3.5 w-3.5 flex-none text-ink-3"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-4.5-4.5" stroke-linecap="round" />
      </svg>
      <input
        ref="input"
        :value="search"
        type="text"
        :placeholder="t('chats.searchHint')"
        class="min-w-0 flex-1 border-0 bg-transparent p-0 text-[calc(12.5px*var(--fs))] text-ink placeholder:text-ink-3 focus:outline-none focus:ring-0"
        @input="$emit('update:search', $event.target.value)"
      />
      <kbd
        class="flex-none rounded-sm border border-line px-[5px] py-px font-mono text-[calc(10px*var(--fs))] text-ink-4"
      >
        /
      </kbd>
    </label>

    <div class="ml-auto flex items-center gap-[7px]">
      <FilterSelect
        :label="statusLabel"
        :options="statusOptions"
        :model-value="status"
        @update:model-value="$emit('update:status', $event)"
      />
      <FilterSelect
        :label="rangeLabel"
        :options="rangeOptions"
        :model-value="range"
        @update:model-value="$emit('update:range', $event)"
      />

      <button
        v-if="selectedCount"
        type="button"
        class="font-display flex h-8 items-center gap-[7px] rounded-md bg-accent px-[13px] text-[calc(12.5px*var(--fs))] font-medium text-accent-on transition-opacity hover:opacity-90 disabled:opacity-50"
        :disabled="selectedCount < 2"
        @click="$emit('merge')"
      >
        <svg
          class="h-3.5 w-3.5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            d="M8 6h12M8 12h12M8 18h12M3.5 6h.01M3.5 12h.01M3.5 18h.01"
            stroke-linecap="round"
          />
        </svg>
        {{ t('chats.bulkMerge.merge') }} {{ selectedCount }}
      </button>

      <button
        type="button"
        class="flex h-8 w-8 items-center justify-center rounded-md border border-line text-ink-2 transition-colors hover:border-ink-4"
        :title="t('common.refresh')"
        :aria-label="t('common.refresh')"
        @click="$emit('refresh')"
      >
        <svg
          class="h-[15px] w-[15px]"
          :class="{ 'animate-spin': loading }"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            d="M20 12a8 8 0 11-2.6-5.9M20 4v4.5h-4.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import FilterSelect from '@/components/ui/FilterSelect.vue'

const props = defineProps({
  search: { type: String, default: '' },
  status: { type: String, default: '' },
  range: { type: String, default: '30' },
  selectedCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false }
})

defineEmits([
  'update:search',
  'update:status',
  'update:range',
  'merge',
  'refresh'
])

const { t } = useI18n()
const input = ref(null)

const statusOptions = computed(() => [
  { value: '', label: t('chats.filterAll') },
  { value: 'fetched', label: t('chats.statePending') },
  { value: 'processing', label: t('chats.stateProcessing') },
  { value: 'success', label: t('chats.stateCompleted') },
  { value: 'failed', label: t('chats.stateFailed') }
])

const rangeOptions = computed(() => [
  { value: '7', label: t('chats.range7') },
  { value: '30', label: t('chats.range30') },
  { value: '90', label: t('chats.range90') },
  { value: '', label: t('chats.rangeAll') }
])

const statusLabel = computed(() => {
  const match = statusOptions.value.find((o) => o.value === props.status)
  return t('chats.statusFilter', { name: match?.label || '' })
})

const rangeLabel = computed(
  () =>
    rangeOptions.value.find((o) => o.value === props.range)?.label ||
    t('chats.rangeAll')
)

// "/" is the search shortcut the field advertises.
const focusOnSlash = (event) => {
  if (event.key !== '/' || event.metaKey || event.ctrlKey) return
  const tag = event.target?.tagName
  if (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    event.target?.isContentEditable
  ) {
    return
  }
  event.preventDefault()
  input.value?.focus()
}

onMounted(() => document.addEventListener('keydown', focusOnSlash))
onBeforeUnmount(() => document.removeEventListener('keydown', focusOnSlash))
</script>
