<template>
  <div class="flex flex-wrap items-center gap-2">
    <template v-for="option in options" :key="option.value">
      <span
        v-if="option.divider"
        class="mx-1 h-4 w-px bg-gray-200"
        aria-hidden="true"
      ></span>
      <button
        v-else
        type="button"
        :aria-pressed="modelValue === option.value"
        class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors"
        :class="
          modelValue === option.value
            ? 'border-primary-600 bg-primary-600 text-white'
            : 'border-gray-200 bg-white text-gray-700 hover:border-primary-400 hover:text-primary-600'
        "
        @click="$emit('update:modelValue', option.value)"
      >
        {{ option.label }}
        <span
          v-if="option.count !== undefined"
          class="tabular-nums text-xs"
          :class="
            modelValue === option.value ? 'text-primary-100' : 'text-gray-400'
          "
        >
          {{ option.count }}
        </span>
      </button>
    </template>
  </div>
</template>

<script setup>
// Status is a dimension of the list, not a level above it, so it filters
// in place with chips instead of opening a second row of tabs.
defineProps({
  options: {
    type: Array,
    default: () => []
  },
  modelValue: {
    type: String,
    default: ''
  }
})

defineEmits(['update:modelValue'])
</script>
