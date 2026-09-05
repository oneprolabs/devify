<template>
  <!-- One icon, one sentence, one clear next step. An empty state with no
       next step is not worth drawing. -->
  <div
    class="flex flex-col items-center justify-center gap-3.5 px-6 py-14 text-center"
  >
    <span
      v-if="$slots.icon"
      class="flex h-12 w-12 items-center justify-center rounded-[14px] bg-accent-soft text-accent"
    >
      <slot name="icon" />
    </span>

    <span class="flex flex-col items-center gap-1.5">
      <span class="text-[calc(15px*var(--fs))] font-semibold text-ink">{{ title }}</span>
      <span
        v-if="description"
        class="max-w-[340px] whitespace-pre-line text-[calc(12.5px*var(--fs))] leading-[1.7] text-ink-3"
      >
        {{ description }}
      </span>
    </span>

    <slot />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' }
})
</script>
