<template>
  <div class="rounded-[9px] border border-line">
    <button
      type="button"
      class="flex h-[42px] w-full items-center gap-[9px] px-3.5 text-ink-2 transition-colors hover:text-ink"
      :aria-expanded="open"
      @click="open = !open"
    >
      <svg
        class="h-3.5 w-3.5 flex-none transition-transform"
        :class="{ 'rotate-90': open }"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        aria-hidden="true"
      >
        <path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span class="text-[12.5px]">{{ label }}</span>
      <slot name="actions" />
    </button>

    <div v-if="open" class="border-t border-line-soft px-3.5 py-3">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  label: { type: String, required: true }
})

const open = ref(false)
</script>
