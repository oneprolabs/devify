<template>
  <div class="flex flex-wrap items-end gap-3">
    <div class="min-w-[180px] flex-1">
      <label class="mb-1 block text-xs text-gray-500">
        {{ t('expense.invoices.search') }}
      </label>
      <input
        :value="modelValue.q"
        type="search"
        class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        :placeholder="t('expense.invoices.searchPlaceholder')"
        @input="update('q', $event.target.value)"
      />
    </div>

    <div v-if="buyers.length">
      <label class="mb-1 block text-xs text-gray-500">
        {{ t('expense.invoices.buyer') }}
      </label>
      <select
        :value="modelValue.buyer"
        class="max-w-[16rem] rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
        @change="update('buyer', $event.target.value)"
      >
        <option value="">{{ t('expense.invoices.allBuyers') }}</option>
        <option v-for="row in buyers" :key="row.name" :value="row.name">
          {{ row.name }} ({{ row.count }})
        </option>
      </select>
    </div>

    <div>
      <label class="mb-1 block text-xs text-gray-500">
        {{ t('expense.invoices.category') }}
      </label>
      <select
        :value="modelValue.category"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
        @change="update('category', $event.target.value)"
      >
        <option value="">{{ t('expense.invoices.allCategories') }}</option>
        <option v-for="key in categories" :key="key" :value="key">
          {{ t(`expense.categories.${key}`) }}
        </option>
      </select>
    </div>

    <label class="flex items-center gap-2 pb-2 text-sm text-gray-700">
      <input
        :checked="modelValue.needsReview"
        type="checkbox"
        class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
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
