<template>
  <button
    v-if="virtualEmail"
    type="button"
    class="flex items-center gap-[11px] rounded border border-line border-l-[3px] border-l-accent bg-panel-sub px-3.5 py-[9px] text-left transition-colors hover:bg-chip"
    :title="t('settings.copyEmail')"
    @click="copyEmail"
  >
    <svg
      class="h-4 w-4 flex-none text-accent"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.9"
      aria-hidden="true"
    >
      <rect x="2.5" y="4.5" width="19" height="15" rx="2.5" />
      <path d="M3 7l9 6 9-6" stroke-linecap="round" stroke-linejoin="round" />
    </svg>

    <span class="flex min-w-0 flex-col gap-px">
      <span class="text-[10px] text-ink-3">{{ label }}</span>
      <span class="truncate font-mono text-[12.5px] text-ink">
        {{ virtualEmail }}
      </span>
    </span>

    <svg
      v-if="!copied"
      class="ml-auto h-3.5 w-3.5 flex-none text-ink-3"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      aria-hidden="true"
    >
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 012-2h10" stroke-linecap="round" />
    </svg>
    <svg
      v-else
      class="ml-auto h-3.5 w-3.5 flex-none text-ok"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      aria-hidden="true"
    >
      <path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  virtualEmail: {
    type: String,
    default: ''
  },
  label: {
    type: String,
    default: ''
  }
})

const { t } = useI18n()

const copied = ref(false)

const copyEmail = async () => {
  if (!props.virtualEmail) return

  try {
    await navigator.clipboard.writeText(props.virtualEmail)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (error) {
    console.error('Failed to copy email:', error)
  }
}
</script>
