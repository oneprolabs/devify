<template>
  <div
    class="flex flex-col gap-3.5 rounded-xl border border-line bg-panel p-4 md:gap-4 md:p-5"
  >
    <div class="flex items-start gap-3 md:gap-[13px]">
      <span
        class="flex h-[38px] w-[38px] flex-none items-center justify-center rounded-[11px] bg-accent-soft text-accent md:h-10 md:w-10"
      >
        <component :is="icon" class="h-[19px] w-[19px] md:h-5 md:w-5" />
      </span>
      <div class="flex min-w-0 flex-col gap-1 md:gap-[5px]">
        <span class="text-[14.5px] font-semibold text-ink md:text-[15px]">
          {{ name }}
        </span>
        <span class="text-xs leading-[1.6] text-ink-3 md:text-[12.5px]">
          {{ description }}
        </span>
      </div>
    </div>

    <!-- Phone: three numbers side by side, then a full-width button.
         Desktop: the same numbers in a rule-divided row with the button
         at its end. -->
    <div
      v-if="stats.length"
      class="flex items-center border-t border-line-soft pt-3 md:pt-3.5"
    >
      <div
        v-for="(stat, index) in stats"
        :key="stat.key"
        class="flex flex-1 flex-col gap-px md:flex-none md:flex-row md:items-baseline md:gap-[7px]"
        :class="[
          index === 0 ? 'md:pr-5' : 'md:px-5',
          index < stats.length - 1 ? 'md:border-r md:border-line-soft' : ''
        ]"
      >
        <span
          class="font-mono text-base font-medium leading-[1.1] md:text-lg md:leading-none"
          :class="stat.tone"
        >
          {{ stat.value }}
        </span>
        <span class="text-[10px] text-ink-3 md:text-[11px]">
          {{ stat.label }}
        </span>
      </div>

      <button
        type="button"
        class="font-display ml-auto hidden h-8 items-center rounded-md bg-accent px-[15px] text-[12.5px] font-medium text-accent-on transition-opacity hover:opacity-90 md:flex"
        @click="$emit('open')"
      >
        {{ t('apps.openApp') }}
      </button>
    </div>

    <div v-if="tags.length" class="hidden gap-[7px] md:flex">
      <span
        v-for="tag in tags"
        :key="tag"
        class="rounded-sm bg-chip px-2 py-[3px] font-mono text-[10.5px] text-ink-2"
      >
        {{ tag }}
      </span>
    </div>

    <button
      type="button"
      class="font-display flex h-11 items-center justify-center rounded-[9px] bg-accent text-[13.5px] font-medium text-accent-on md:hidden"
      @click="$emit('open')"
    >
      {{ t('apps.openApp') }}
    </button>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  name: { type: String, required: true },
  description: { type: String, default: '' },
  icon: { type: [Object, Function], required: true },
  // [{ key, value, label, tone }] — tone is a text colour class or ''.
  stats: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] }
})

defineEmits(['open'])

const { t } = useI18n()
</script>
