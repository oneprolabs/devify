<template>
  <div
    class="inline-flex items-center gap-0.5 rounded-lg border border-line bg-panel-sub p-0.5"
    role="group"
    :aria-label="t('theme.label')"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      class="rounded-md px-2 py-1 text-[calc(11px*var(--fs))] transition-colors"
      :class="
        mode === option.value
          ? 'bg-panel text-ink shadow-sm'
          : 'text-ink-3 hover:text-ink'
      "
      :title="option.label"
      :aria-pressed="mode === option.value"
      @click.stop="setMode(option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTheme } from '@/composables/useTheme'

const { t } = useI18n()
const { mode, setMode } = useTheme()

const options = computed(() => [
  { value: 'light', label: t('theme.light') },
  { value: 'dark', label: t('theme.dark') },
  { value: 'system', label: t('theme.system') }
])
</script>
