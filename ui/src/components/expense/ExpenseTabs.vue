<template>
  <!-- Three resources, not three states. On a wide screen these sit at the
       right end of the title row; a phone has no room there, so the
       artboard gives them a full-width band under the header instead. -->
  <div
    class="flex items-center overflow-hidden rounded-md border border-line"
    :class="full ? 'h-9 w-full' : 'h-8 flex-none'"
    role="tablist"
  >
    <button
      v-for="(tab, index) in tabs"
      :key="tab.value"
      type="button"
      role="tab"
      class="font-display flex h-full items-center justify-center text-[calc(12.5px*var(--fs))] transition-colors"
      :class="[
        full ? 'flex-1' : 'px-3.5',
        modelValue === tab.value
          ? 'bg-accent-soft font-medium text-accent'
          : 'text-ink-2 hover:bg-chip',
        index ? 'border-l border-line' : ''
      ]"
      :aria-selected="modelValue === tab.value"
      @click="$emit('update:modelValue', tab.value)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, required: true },
  tabs: { type: Array, required: true },
  // Full width under the header on a phone; intrinsic width in the header
  // on a wide screen.
  full: { type: Boolean, default: false }
})

defineEmits(['update:modelValue'])
</script>
