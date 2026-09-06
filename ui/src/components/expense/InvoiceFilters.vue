<template>
  <div class="flex flex-wrap items-end gap-3">
    <div class="flex min-w-[180px] flex-1 flex-col gap-[5px]">
      <label class="text-[calc(10.5px*var(--fs))] text-ink-3">
        {{ t('expense.invoices.search') }}
      </label>
      <div
        class="flex h-[34px] items-center gap-2 rounded-md border border-line bg-panel px-[11px]"
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
          :value="modelValue.q"
          type="search"
          class="min-w-0 flex-1 border-0 bg-transparent p-0 text-[calc(12.5px*var(--fs))] text-ink placeholder:text-ink-4 focus:outline-none focus:ring-0"
          :placeholder="t('expense.invoices.searchPlaceholder')"
          @input="update('q', $event.target.value)"
        />
      </div>
    </div>

    <div v-if="buyers.length" class="flex flex-col gap-[5px]">
      <label class="text-[calc(10.5px*var(--fs))] text-ink-3">
        {{ t('expense.invoices.buyer') }}
      </label>
      <select
        :value="modelValue.buyer"
        class="h-[34px] w-[254px] rounded-md border border-line bg-panel px-[11px] text-[calc(12.5px*var(--fs))] text-ink-2 focus:border-accent focus:outline-none"
        @change="update('buyer', $event.target.value)"
      >
        <option value="">{{ t('expense.invoices.allBuyers') }}</option>
        <option v-for="row in buyers" :key="row.name" :value="row.name">
          {{ row.name }} ({{ row.count }})
        </option>
      </select>
    </div>

    <div class="flex flex-col gap-[5px]">
      <label class="text-[calc(10.5px*var(--fs))] text-ink-3">
        {{ t('expense.invoices.category') }}
      </label>
      <select
        :value="modelValue.category"
        class="h-[34px] w-[174px] rounded-md border border-line bg-panel px-[11px] text-[calc(12.5px*var(--fs))] text-ink-2 focus:border-accent focus:outline-none"
        @change="update('category', $event.target.value)"
      >
        <option value="">{{ t('expense.invoices.allCategories') }}</option>
        <option v-for="key in categories" :key="key" :value="key">
          {{ t(`expense.categories.${key}`) }}
        </option>
      </select>
    </div>

    <label class="flex h-[34px] items-center gap-[7px] text-[calc(12.5px*var(--fs))] text-ink-2">
      <input
        :checked="modelValue.needsReview"
        type="checkbox"
        class="h-[17px] w-[17px] rounded-sm border-line text-accent focus:ring-accent"
        @change="update('needsReview', $event.target.checked)"
      />
      {{ t('expense.invoices.needsReviewOnly') }}
    </label>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  },
  // Derived from the invoices themselves rather than configured, so the
  // list always matches what actually arrived.
  buyers: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()

const categories = [
  'transport_long',
  'transport_local',
  'accommodation',
  'meals',
  'entertainment',
  'office',
  'communication',
  'training',
  'other'
]

function update(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>
