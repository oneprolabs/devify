<template>
  <section class="rounded-lg border border-line bg-panel">
    <header
      v-if="title || $slots.header || $slots.actions"
      class="flex items-center gap-2 border-b border-line-soft px-4"
      :class="dense ? 'h-[38px]' : 'h-10'"
    >
      <slot name="icon" />
      <span
        class="font-semibold text-ink"
        :class="dense ? 'text-[12.5px]' : 'text-[13px]'"
      >
        {{ title }}
      </span>
      <span v-if="meta" class="font-mono text-[11px] text-ink-3">{{
        meta
      }}</span>
      <slot name="header" />
      <div v-if="$slots.actions" class="ml-auto flex items-center gap-3">
        <slot name="actions" />
      </div>
    </header>

    <div :class="bodyClass">
      <slot />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  // A count or short note beside the title.
  meta: { type: String, default: '' },
  // Side-panel cards use the shorter 38px header.
  dense: { type: Boolean, default: false },
  // Rows draw their own padding and dividers, so they opt out of the body's.
  flush: { type: Boolean, default: false }
})

const bodyClass = computed(() =>
  props.flush ? '' : props.dense ? 'px-4 py-3' : 'px-4 py-3.5'
)
</script>
