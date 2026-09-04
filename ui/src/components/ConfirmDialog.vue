<template>
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0"
    leave-active-class="transition duration-150 ease-in"
    leave-to-class="opacity-0"
  >
    <div v-if="show" class="fixed inset-0 z-50 overflow-y-auto">
      <div class="flex min-h-full items-center justify-center p-4">
        <div class="fixed inset-0 bg-ink/40" aria-hidden="true"></div>

        <div
          class="relative flex w-full max-w-lg flex-col overflow-hidden rounded-xl border border-line bg-panel shadow-soft-lg"
          role="dialog"
          aria-modal="true"
        >
          <div class="flex items-start gap-[13px] px-5 pb-3.5 pt-[18px]">
            <span
              class="flex h-[34px] w-[34px] flex-none items-center justify-center rounded-[10px]"
              :class="TONES[variant].tile"
            >
              <svg
                class="h-[17px] w-[17px]"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <path
                  :d="TONES[variant].icon"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </span>

            <div class="flex min-w-0 flex-1 flex-col gap-[7px]">
              <h3 v-if="title" class="text-[15px] font-semibold text-ink">
                {{ title }}
              </h3>
              <p class="text-[12.5px] leading-[1.75] text-ink-2">
                {{ message }}
              </p>
              <slot />

              <!-- An irreversible action asks for the name back, so it cannot
                   be confirmed by muscle memory. -->
              <div v-if="confirmPhrase" class="flex flex-col gap-1.5 pt-0.5">
                <span class="text-[11.5px] text-ink-3">
                  {{ t('common.typeToConfirm', { phrase: confirmPhrase }) }}
                </span>
                <input
                  v-model="typed"
                  type="text"
                  class="h-9 rounded border border-line bg-panel px-3 font-mono text-[12.5px] text-ink placeholder:text-ink-4 focus:border-accent focus:outline-none focus:ring-0"
                  :placeholder="confirmPhrase"
                />
              </div>
            </div>
          </div>

          <div
            class="flex justify-end gap-[9px] border-t border-line-soft bg-panel-sub px-5 py-3"
          >
            <button
              type="button"
              class="font-display flex h-[34px] items-center rounded border border-line px-[15px] text-[12.5px] text-ink-2 transition-colors hover:border-ink-4 disabled:opacity-50"
              :disabled="loading"
              @click="handleClose"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="button"
              class="font-display flex h-[34px] items-center rounded px-4 text-[12.5px] font-medium transition-opacity hover:opacity-90 disabled:opacity-45"
              :class="TONES[variant].button"
              :disabled="loading || !canConfirm"
              @click="handleConfirm"
            >
              {{ confirmText || t('common.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '' },
  message: { type: String, required: true },
  confirmText: { type: String, default: '' },
  variant: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'danger', 'warning'].includes(value)
  },
  // When set, the reader must type this exact text before confirming.
  confirmPhrase: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'confirm'])

const { t } = useI18n()

const TONES = {
  primary: {
    tile: 'bg-accent-soft text-accent',
    button: 'bg-accent text-accent-on',
    icon: 'M12 16v-4M12 8h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
  },
  warning: {
    tile: 'bg-warn-soft text-warn',
    button: 'bg-accent text-accent-on',
    icon: 'M20 12a8 8 0 11-2.6-5.9M20 4v4.5h-4.5'
  },
  danger: {
    tile: 'bg-bad-soft text-bad',
    button: 'bg-bad text-accent-on',
    icon: 'M5 7h14M10 11v6M14 11v6M6.5 7l.8 12a1 1 0 001 1h7.4a1 1 0 001-1l.8-12M9.5 7V4.5h5V7'
  }
}

const typed = ref('')

const canConfirm = computed(
  () => !props.confirmPhrase || typed.value.trim() === props.confirmPhrase
)

// Reopening must not inherit the last answer.
watch(
  () => props.show,
  (open) => {
    if (open) typed.value = ''
  }
)

const handleClose = () => emit('close')
const handleConfirm = () => {
  if (canConfirm.value) emit('confirm')
}
</script>
