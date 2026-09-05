<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="buttonClasses"
    :aria-label="loading ? 'Loading...' : undefined"
    :aria-disabled="disabled || loading"
    @click="handleClick"
    @keydown="handleKeydown"
  >
    <svg
      v-if="loading"
      class="animate-spin -ml-1 mr-2 h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        class="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        stroke-width="4"
      ></circle>
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      ></path>
    </svg>
    <slot />
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (value) =>
      ['primary', 'secondary', 'danger', 'outline', 'warning'].includes(value)
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg'].includes(value)
  },
  type: {
    type: String,
    default: 'button'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  block: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['click'])

const handleClick = (event) => {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}

const handleKeydown = (event) => {
  if (
    (event.key === 'Enter' || event.key === ' ') &&
    !props.disabled &&
    !props.loading
  ) {
    event.preventDefault()
    emit('click', event)
  }
}

const buttonClasses = computed(() => {
  const baseClasses = 'btn'
  const variantClasses = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    danger: 'btn-danger',
    outline: 'btn-outline',
    warning: 'btn-warning'
  }
  const sizeClasses = {
    sm: 'h-7 px-2.5 text-[calc(11.5px*var(--fs))]',
    md: 'h-8 px-[13px] text-[calc(12.5px*var(--fs))]',
    lg: 'h-11 rounded-[9px] px-4 text-sm font-semibold'
  }
  const blockClass = props.block ? 'w-full' : ''

  return [
    baseClasses,
    variantClasses[props.variant],
    sizeClasses[props.size],
    blockClass
  ]
    .filter(Boolean)
    .join(' ')
})
</script>
