<template>
  <div class="flex flex-col gap-1.5">
    <label
      v-if="label"
      :for="inputId"
      class="text-xs text-ink-2"
    >
      {{ label }}
    </label>

    <div class="relative">
      <input
        :id="inputId"
        :type="revealed ? 'text' : type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :required="required"
        :autocomplete="autocomplete"
        :class="inputClasses"
        @input="$emit('update:modelValue', $event.target.value)"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />

      <button
        v-if="type === 'password'"
        type="button"
        class="absolute inset-y-0 right-0 flex items-center pr-3 text-ink-3 transition-colors hover:text-ink-2"
        :aria-label="revealed ? t('common.hide') : t('common.show')"
        @click="revealed = !revealed"
      >
        <svg
          class="h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.9"
          aria-hidden="true"
        >
          <path
            d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"
          />
          <circle cx="12" cy="12" r="2.6" />
          <path v-if="revealed" d="M4 20L20 4" stroke-linecap="round" />
        </svg>
      </button>

      <div
        v-if="$slots.icon"
        class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"
      >
        <slot name="icon" />
      </div>

      <div
        v-if="error && showValidationIcon"
        class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none"
      >
        <svg class="w-5 h-5 text-bad" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clip-rule="evenodd"
          />
        </svg>
      </div>

      <div
        v-else-if="valid && !error"
        class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none"
      >
        <svg class="w-5 h-5 text-ok" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
            clip-rule="evenodd"
          />
        </svg>
      </div>

      <div
        v-else-if="$slots.rightIcon"
        class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none"
      >
        <slot name="rightIcon" />
      </div>
    </div>

    <p v-if="error" class="text-[calc(11.5px*var(--fs))] text-bad">
      {{ error }}
    </p>

    <p v-else-if="help" class="text-[calc(11.5px*var(--fs))] text-ink-3">
      {{ help }}
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: ''
  },
  type: {
    type: String,
    default: 'text'
  },
  label: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  autocomplete: {
    type: String,
    default: ''
  },
  help: {
    type: String,
    default: ''
  },
  error: {
    type: String,
    default: ''
  },
  valid: {
    type: Boolean,
    default: false
  },
  showValidationIcon: {
    type: Boolean,
    default: false
  },
  required: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg'].includes(value)
  }
})

defineEmits(['update:modelValue', 'blur', 'focus'])

const { t } = useI18n()
const revealed = ref(false)
const inputId = ref(`input-${Math.random().toString(36).substr(2, 9)}`)

const inputClasses = computed(() => {
  const baseClasses = 'input'
  const errorClass = props.error ? 'input-error' : ''
  const sizeClasses = {
    sm: 'px-2 py-1 text-[calc(11.5px*var(--fs))] leading-4',
    md: '',
    lg: 'rounded-[9px] px-[13px] py-[11px] text-[calc(13px*var(--fs))] leading-5'
  }
  const iconPadding = props.$slots?.icon ? 'pl-10' : ''
  const hasRightIcon =
    (props.valid && !props.error) ||
    (props.error && props.showValidationIcon) ||
    props.$slots?.rightIcon
  const rightIconPadding = hasRightIcon ? 'pr-10' : ''

  return [
    baseClasses,
    errorClass,
    sizeClasses[props.size],
    iconPadding,
    rightIconPadding
  ]
    .filter(Boolean)
    .join(' ')
})
</script>
