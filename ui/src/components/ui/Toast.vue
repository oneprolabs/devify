<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition ease-out duration-300"
      enter-from-class="opacity-0 translate-x-4"
      enter-to-class="opacity-100 translate-x-0"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="opacity-100 translate-x-0"
      leave-to-class="opacity-0 translate-x-4"
    >
      <div
        v-if="state.show"
        class="fixed left-4 right-4 top-4 flex max-w-sm gap-[11px] rounded-[9px] border border-line border-l-[3px] bg-panel px-3.5 py-3 shadow-soft-md sm:left-auto"
        :class="edgeClasses[state.type]"
        style="z-index: 9999"
        role="alert"
      >
        <component
          :is="iconComponent"
          class="mt-px h-[17px] w-[17px] flex-shrink-0"
          :class="iconClasses[state.type]"
        />
        <p class="min-w-0 flex-1 text-[calc(13px*var(--fs))] font-semibold text-ink">
          {{ state.message }}
        </p>
        <button
          type="button"
          class="mt-0.5 flex-shrink-0 text-ink-4 transition-colors hover:text-ink-2"
          :title="t('common.close')"
          @click="handleClose"
        >
          <svg
            class="h-3.5 w-3.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            aria-hidden="true"
          >
            <path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
          </svg>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const { state, hide } = useToast()

// The tone lives in a 3px edge, not a tinted panel: a toast should read as
// the app's own surface with a stripe saying how it went.
const edgeClasses = {
  success: 'border-l-ok',
  error: 'border-l-bad',
  warning: 'border-l-warn',
  info: 'border-l-accent'
}

const iconClasses = {
  success: 'text-ok',
  error: 'text-bad',
  warning: 'text-warn',
  info: 'text-accent'
}

const SuccessIcon = () =>
  h('svg', { viewBox: '0 0 20 20', fill: 'currentColor' }, [
    h('path', {
      'fill-rule': 'evenodd',
      d: 'M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z',
      'clip-rule': 'evenodd'
    })
  ])

const ErrorIcon = () =>
  h('svg', { viewBox: '0 0 20 20', fill: 'currentColor' }, [
    h('path', {
      'fill-rule': 'evenodd',
      d: 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z',
      'clip-rule': 'evenodd'
    })
  ])

const WarningIcon = () =>
  h('svg', { viewBox: '0 0 20 20', fill: 'currentColor' }, [
    h('path', {
      'fill-rule': 'evenodd',
      d: 'M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z',
      'clip-rule': 'evenodd'
    })
  ])

const InfoIcon = () =>
  h('svg', { viewBox: '0 0 20 20', fill: 'currentColor' }, [
    h('path', {
      'fill-rule': 'evenodd',
      d: 'M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z',
      'clip-rule': 'evenodd'
    })
  ])

const iconComponent = computed(() => {
  const icons = {
    success: SuccessIcon,
    error: ErrorIcon,
    warning: WarningIcon,
    info: InfoIcon
  }
  return icons[state.type] || InfoIcon
})

const handleClose = () => {
  hide()
}
</script>
