<template>
  <div class="flex flex-wrap items-center gap-2">
    <template v-for="option in options" :key="option.value">
      <span
        v-if="option.divider"
        class="mx-1 h-4 w-px bg-chip"
        aria-hidden="true"
      ></span>
      <button
        v-else
        type="button"
        :aria-pressed="modelValue === option.value"
        class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors"
        :class="
          modelValue === option.value
            ? 'border-accent bg-accent text-accent-on'
            : 'border-line bg-panel text-ink-2 hover:border-accent hover:text-accent'
        "
        @click="$emit('update:modelValue', option.value)"
      >
        {{ option.label }}
        <span
          v-if="option.count !== undefined"
          class="tabular-nums text-xs"
          :class="modelValue === option.value ? 'text-accent-on' : 'text-ink-4'"
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
