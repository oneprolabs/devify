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
        class="flex h-[30px] items-center gap-1.5 rounded-md border px-[11px] text-xs transition-colors"
        :class="
          modelValue === option.value
            ? 'border-accent bg-accent-soft text-accent'
            : 'border-line bg-panel text-ink-2 hover:border-accent hover:text-accent'
        "
        @click="$emit('update:modelValue', option.value)"
      >
        {{ option.label }}
        <span
          v-if="option.count !== undefined"
          class="font-mono text-[calc(10.5px*var(--fs))] opacity-70"
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
