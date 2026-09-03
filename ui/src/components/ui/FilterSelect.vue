<template>
  <div ref="root" class="relative">
    <button
      type="button"
      class="flex h-8 items-center gap-1.5 rounded-md border border-line px-[11px] text-[12.5px] text-ink-2 transition-colors hover:border-ink-4"
      @click="open = !open"
    >
      {{ label }}
      <svg
        class="h-3 w-3"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.3"
        aria-hidden="true"
      >
        <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <div
      v-if="open"
      class="absolute right-0 z-30 mt-1 min-w-[150px] rounded-md border border-line bg-panel py-1 shadow-soft-md"
    >
      <button
        v-for="option in options"
        :key="String(option.value)"
        type="button"
        class="flex w-full items-center px-3 py-1.5 text-left text-[12.5px] transition-colors hover:bg-chip"
        :class="option.value === modelValue ? 'text-accent' : 'text-ink-2'"
        @click="pick(option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

defineProps({
  // Text on the closed control; it already carries the field name.
  label: { type: String, required: true },
  options: { type: Array, required: true },
  modelValue: { type: [String, Number, null], default: null }
})

const emit = defineEmits(['update:modelValue'])

const root = ref(null)
const open = ref(false)

const pick = (value) => {
  emit('update:modelValue', value)
  open.value = false
}

const closeOnOutside = (event) => {
  if (open.value && root.value && !root.value.contains(event.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', closeOnOutside))
onBeforeUnmount(() => document.removeEventListener('click', closeOnOutside))
</script>
