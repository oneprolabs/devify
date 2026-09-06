<template>
  <div
    class="inline-flex items-center gap-0.5 rounded-lg border border-line bg-panel-sub p-0.5"
    role="group"
    :aria-label="t('fontSize.label')"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      class="rounded-md px-2 py-1 text-[calc(11px*var(--fs))] transition-colors"
      :class="
        size === option.value
          ? 'bg-panel text-ink shadow-sm'
          : 'text-ink-3 hover:text-ink'
      "
      :title="option.label"
      :aria-pressed="size === option.value"
      @click.stop="setSize(option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFontScale } from '@/composables/useFontScale'

const { t } = useI18n()
const { size, setSize } = useFontScale()

const options = computed(() => [
  { value: 'standard', label: t('fontSize.standard') },
  { value: 'large', label: t('fontSize.large') }
])
</script>
