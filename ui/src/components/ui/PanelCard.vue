<template>
  <section class="rounded-lg border border-line bg-panel">
    <header
      v-if="title || $slots.header || $slots.actions"
      class="flex items-center gap-2 border-b border-line-soft px-4"
      :class="dense ? 'h-9' : 'h-[38px]'"
    >
      <slot name="icon" />
      <span
        class="font-semibold text-ink"
        :class="dense ? 'text-[calc(12.5px*var(--fs))]' : 'text-[calc(13px*var(--fs))]'"
      >
        {{ title }}
      </span>
      <span v-if="meta" class="font-mono text-[calc(11px*var(--fs))] text-ink-3">{{
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
  // Side-panel cards use the shorter 36px header and tighter body.
  dense: { type: Boolean, default: false },
  // Rows draw their own padding and dividers, so they opt out of the body's.
  flush: { type: Boolean, default: false }
})

// The canvas draws the detail panel's main cards with a 38px header over
// 14/16 padding, and the narrower side cards with a 36px header over 11/15.
const bodyClass = computed(() =>
  props.flush ? '' : props.dense ? 'px-[15px] py-[11px]' : 'px-4 py-3.5'
)
</script>
