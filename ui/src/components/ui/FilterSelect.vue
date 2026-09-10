<template>
  <div ref="root" class="relative">
    <button
      ref="trigger"
      type="button"
      class="flex items-center gap-1.5 rounded-md border border-line text-ink-2 transition-colors hover:border-ink-4"
      :class="
        size === 'sm'
          ? 'h-[30px] bg-panel px-[11px] text-xs'
          : 'h-8 px-[11px] text-[calc(12.5px*var(--fs))]'
      "
      @click="toggleOpen"
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

    <Teleport to="body">
      <div
        v-if="open"
        data-filter-select-menu
        class="fixed z-30 min-w-[150px] rounded-md border border-line bg-panel py-1 shadow-soft-md"
        :style="menuStyle"
      >
        <button
          v-for="option in options"
          :key="String(option.value)"
          type="button"
          class="flex w-full items-center px-3 py-1.5 text-left text-[calc(12.5px*var(--fs))] transition-colors hover:bg-chip"
          :class="option.value === modelValue ? 'text-accent' : 'text-ink-2'"
          @click="pick(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

defineProps({
  // Text on the closed control; it already carries the field name.
  label: { type: String, required: true },
  options: { type: Array, required: true },
  // The canvas draws these at 32px in a page header and 30px on a filter
  // bar, where they sit on the panel rather than the bar's tint.
  size: { type: String, default: 'md' },
  modelValue: { type: [String, Number, null], default: null }
})

const emit = defineEmits(['update:modelValue'])

const root = ref(null)
const trigger = ref(null)
const open = ref(false)
const menuStyle = ref({})

const updateMenuPosition = () => {
  if (!trigger.value || typeof window === 'undefined') return

  const rect = trigger.value.getBoundingClientRect()
  menuStyle.value = {
    top: `${rect.bottom + 4}px`,
    right: `${Math.max(8, window.innerWidth - rect.right)}px`
  }
}

const removePositionListeners = () => {
  if (typeof window === 'undefined') return
  window.removeEventListener('resize', updateMenuPosition)
  window.removeEventListener('scroll', updateMenuPosition, true)
}

const addPositionListeners = () => {
  if (typeof window === 'undefined') return
  window.addEventListener('resize', updateMenuPosition)
  window.addEventListener('scroll', updateMenuPosition, true)
}

const close = () => {
  open.value = false
  removePositionListeners()
}

const toggleOpen = () => {
  open.value = !open.value
  if (open.value) {
    updateMenuPosition()
    addPositionListeners()
  } else {
    close()
  }
}

const pick = (value) => {
  emit('update:modelValue', value)
  close()
}

const closeOnOutside = (event) => {
  if (open.value && root.value && !root.value.contains(event.target)) {
    close()
  }
}

onMounted(() => document.addEventListener('click', closeOnOutside))
onBeforeUnmount(() => {
  document.removeEventListener('click', closeOnOutside)
  removePositionListeners()
})
</script>
