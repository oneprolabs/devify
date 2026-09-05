<template>
  <header
    class="flex h-[60px] flex-shrink-0 items-center justify-between border-b border-line bg-app px-4 md:px-10"
  >
    <div class="flex min-w-0 items-center gap-2.5">
      <img
        src="/android-chrome-192x192.png"
        alt=""
        class="h-[26px] w-[26px] flex-none rounded-[7px]"
      />
      <span class="font-display text-base font-semibold text-ink">
        {{ t('common.appName') }}
      </span>
      <span class="hidden text-[calc(12.5px*var(--fs))] text-ink-4 sm:block">
        {{ t('share.viewSubtitle') }}
      </span>
    </div>

    <div class="flex items-center gap-3.5">
      <LanguageSwitcher />
      <button
        type="button"
        class="font-display flex h-8 items-center gap-[7px] rounded-md border border-line px-[13px] text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:border-ink-4"
        @click="copyLink"
      >
        <svg
          v-if="!copied"
          class="h-3.5 w-3.5"
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
          class="h-3.5 w-3.5 text-ok"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            d="M5 13l4 4L19 7"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <span class="hidden sm:inline">
          {{ copied ? t('share.copied') : t('share.copyLink') }}
        </span>
      </button>
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '@/components/ui/LanguageSwitcher.vue'

const { t } = useI18n()
const copied = ref(false)

// The address bar already holds the link; this saves the reader selecting it.
const copyLink = async () => {
  try {
    await navigator.clipboard.writeText(window.location.href)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (error) {
    console.error('Failed to copy share link:', error)
  }
}
</script>
