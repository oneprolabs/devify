<template>
  <div class="flex flex-col gap-5 p-4 md:p-6">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:gap-3">
      <label
        class="flex h-9 items-center gap-2.5 rounded border border-line bg-panel px-3 md:w-[366px]"
      >
        <svg
          class="h-[15px] w-[15px] flex-none text-ink-3"
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
          v-model="search"
          type="text"
          :placeholder="t('relay.searchTypes')"
          class="min-w-0 flex-1 border-0 bg-transparent p-0 text-[calc(12.5px*var(--fs))] text-ink placeholder:text-ink-3 focus:outline-none focus:ring-0"
        />
      </label>

      <div class="flex gap-[7px] overflow-x-auto">
        <button
          v-for="filter in filters"
          :key="filter.key"
          type="button"
          class="font-display flex-none rounded-md px-[13px] py-[7px] text-xs transition-colors"
          :class="
            category === filter.key
              ? 'bg-accent font-medium text-accent-on'
              : 'border border-line text-ink-2'
          "
          @click="category = filter.key"
        >
          {{ filter.label }} {{ filter.count }}
        </button>
      </div>
    </div>

    <div v-for="group in groups" :key="group.key" class="flex flex-col gap-3">
      <span class="font-mono text-[calc(10.5px*var(--fs))] tracking-[0.06em] text-ink-4">{{
        group.label
      }}</span>
      <div class="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
        <button
          v-for="type in group.types"
          :key="type.value"
          type="button"
          class="flex flex-col gap-[11px] rounded-[11px] border p-4 text-left transition-colors"
          :class="
            modelValue === type.value
              ? 'border-accent bg-accent-soft'
              : 'border-line bg-panel hover:border-ink-4'
          "
          @click="$emit('update:modelValue', type.value)"
        >
          <span class="flex items-start gap-[11px]">
            <span
              class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] font-mono text-[calc(11px*var(--fs))] font-semibold"
              :class="
                modelValue === type.value
                  ? 'bg-panel text-accent'
                  : 'bg-chip text-ink-2'
              "
            >
              {{ TYPE_INITIALS[type.value] }}
            </span>
            <span class="flex min-w-0 flex-col gap-[3px]">
              <span
                class="text-sm font-semibold"
                :class="modelValue === type.value ? 'text-accent' : 'text-ink'"
              >
                {{ t(TYPE_LABEL_KEYS[type.value]) }}
              </span>
              <span
                class="font-mono text-[calc(10.5px*var(--fs))]"
                :class="
                  modelValue === type.value
                    ? 'text-accent opacity-75'
                    : 'text-ink-4'
                "
              >
                {{
                  t('relay.existingChannels', { count: countFor(type.value) })
                }}
              </span>
            </span>
            <svg
              v-if="modelValue === type.value"
              class="ml-auto h-[17px] w-[17px] flex-none text-accent"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.4"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="9" stroke-width="1.6" />
              <path
                d="M8 12.3l2.7 2.7L16 9.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </span>

          <span
            class="text-[calc(11.5px*var(--fs))] leading-[1.65]"
            :class="
              modelValue === type.value
                ? 'text-accent opacity-85'
                : 'text-ink-3'
            "
          >
            {{ t(type.descriptionKey) }}
          </span>

          <span class="flex flex-wrap gap-[5px]">
            <span
              v-for="action in type.actions"
              :key="action.key"
              class="rounded-sm px-1.5 py-px font-mono text-[calc(9.5px*var(--fs))]"
              :class="actionClass(action, modelValue === type.value)"
            >
              {{ t(ACTION_LABEL_KEYS[action.key]) }}
              <template v-if="action.support === 'partial'">
                · {{ t('relay.partialSupport') }}
              </template>
            </span>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CHANNEL_CATEGORIES,
  CHANNEL_TYPES,
  TYPE_INITIALS,
  TYPE_LABEL_KEYS
} from './channelTypes'

const props = defineProps({
  modelValue: { type: String, default: '' },
  // Existing channels, so each card can say how many are already set up.
  channels: { type: Array, default: () => [] }
})

defineEmits(['update:modelValue'])

const { t } = useI18n()
const search = ref('')
const category = ref('all')

const matching = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return CHANNEL_TYPES
  return CHANNEL_TYPES.filter((type) =>
    t(TYPE_LABEL_KEYS[type.value]).toLowerCase().includes(term)
  )
})

const filters = computed(() => [
  { key: 'all', label: t('todos.filters.all'), count: matching.value.length },
  ...CHANNEL_CATEGORIES.map((entry) => ({
    key: entry.key,
    label: t(entry.labelKey),
    count: matching.value.filter((type) => type.category === entry.key).length
  }))
])

const groups = computed(() =>
  CHANNEL_CATEGORIES.filter(
    (entry) => category.value === 'all' || category.value === entry.key
  )
    .map((entry) => ({
      key: entry.key,
      label: t(entry.labelKey),
      types: matching.value.filter((type) => type.category === entry.key)
    }))
    .filter((group) => group.types.length)
)

const countFor = (value) =>
  props.channels.filter((channel) => channel.target_type === value).length

const ACTION_LABEL_KEYS = {
  new: 'relay.actionNew2',
  link: 'relay.actionLink',
  update: 'relay.actionUpdate2'
}

const actionClass = (action, selected) => {
  if (selected) return 'border border-accent text-accent opacity-80'
  return action.support === 'partial'
    ? 'bg-warn-soft text-warn'
    : 'bg-chip text-ink-3'
}
</script>
