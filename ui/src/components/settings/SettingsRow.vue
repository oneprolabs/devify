<template>
  <div class="flex flex-col gap-3 md:flex-row md:gap-7">
    <div class="flex flex-col gap-1 pt-0.5 md:w-44 md:flex-none">
      <span class="text-[calc(13px*var(--fs))] font-semibold text-ink">{{ title }}</span>
      <span v-if="description" class="text-[calc(11.5px*var(--fs))] leading-[1.6] text-ink-3">
        {{ description }}
      </span>
    </div>
    <div class="flex min-w-0 flex-1 flex-col gap-2.5 md:max-w-[640px]">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' }
})
</script>
