<template>
  <nav
    class="flex flex-shrink-0 gap-1 overflow-x-auto border-b border-line p-3 md:w-[236px] md:flex-col md:gap-[3px] md:flex-1 md:overflow-visible md:border-b-0 md:p-3"
  >
    <button
      v-for="section in sections"
      :key="section.value"
      type="button"
      class="flex flex-none flex-col gap-0.5 rounded px-3 py-2.5 text-left transition-colors"
      :class="modelValue === section.value ? 'bg-accent-soft' : 'hover:bg-chip'"
      @click="$emit('update:modelValue', section.value)"
    >
      <span
        class="text-[calc(13px*var(--fs))]"
        :class="
          modelValue === section.value
            ? 'font-semibold text-accent'
            : 'font-medium text-ink-2'
        "
      >
        {{ section.label }}
      </span>
      <span
        class="hidden text-[calc(11px*var(--fs))] leading-[1.5] md:block"
        :class="
          modelValue === section.value ? 'text-accent opacity-75' : 'text-ink-3'
        "
      >
        {{ section.description }}
      </span>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  modelValue: { type: String, required: true },
  // [{ value, label, description }]
  sections: { type: Array, required: true }
})

defineEmits(['update:modelValue'])
</script>
