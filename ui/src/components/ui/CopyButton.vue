<template>
  <button
    @click.stop="handleCopy"
    class="p-1 text-ink-4 hover:text-ink-2 hover:bg-chip rounded transition-colors flex-shrink-0"
    :title="t('common.copy')"
  >
    <svg
      class="w-3.5 h-3.5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      />
    </svg>
  </button>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  text: {
    type: String,
    required: true
  }
})

const { t } = useI18n()
const { showSuccess } = useToast()

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.text)
    showSuccess(t('common.copied'))
  } catch (error) {
    console.error('Failed to copy text:', error)
  }
}
</script>
