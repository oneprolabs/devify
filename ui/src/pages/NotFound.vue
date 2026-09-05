<template>
  <AppLayout :padded="false">
    <!-- The canvas keeps the existing words and drops the gradients and
         floating particles: a 404 should be quiet, not decorated. -->
    <div class="flex min-h-0 flex-1 items-center justify-center p-6">
      <div
        class="flex w-full max-w-[560px] flex-col items-center gap-3.5 rounded-[11px] border border-line bg-panel px-6 py-14 text-center"
      >
        <span
          class="font-display text-[calc(56px*var(--fs))] font-bold leading-none tracking-[-0.03em] text-line"
        >
          {{ t('notFound.title') }}
        </span>

        <div class="flex max-w-[400px] flex-col items-center gap-2">
          <p class="text-[calc(14.5px*var(--fs))] font-semibold text-ink">
            {{ t('notFound.quote') }}
          </p>
          <p class="text-[calc(12.5px*var(--fs))] leading-[1.75] text-ink-3">
            {{ t('notFound.description') }}
          </p>
        </div>

        <span class="h-px w-[52px] bg-line"></span>

        <p class="text-[calc(11.5px*var(--fs))] italic leading-[1.7] text-ink-4">
          {{ t('notFound.philosophy') }}
        </p>

        <div class="flex gap-[9px] pt-1">
          <button
            type="button"
            class="font-display flex h-[34px] items-center rounded px-[15px] text-[calc(12.5px*var(--fs))] font-medium text-accent-on transition-opacity bg-accent hover:opacity-90"
            @click="goHome"
          >
            {{ t('notFound.returnHome') }}
          </button>
          <button
            type="button"
            class="font-display flex h-[34px] items-center rounded border border-line px-[15px] text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:border-ink-4"
            @click="goBack"
          >
            {{ t('notFound.goBack') }}
          </button>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'

const router = useRouter()
const { t } = useI18n()

const goHome = () => {
  router.push('/chats')
}

const goBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/chats')
  }
}
</script>
