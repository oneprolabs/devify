<template>
  <div class="flex items-center gap-[7px]">
    <button
      type="button"
      class="flex h-8 items-center gap-[7px] rounded-md border border-line px-3 text-[12.5px] text-ink-2 transition-colors hover:border-ink-4 disabled:opacity-50"
      :disabled="busy"
      @click="$emit('retry')"
    >
      <svg
        class="h-3.5 w-3.5"
        :class="{ 'animate-spin': retrying }"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path
          d="M20 12a8 8 0 11-2.6-5.9M20 4v4.5h-4.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      <span class="hidden lg:inline">{{ t('chats.detail.reprocess') }}</span>
    </button>

    <button
      type="button"
      class="flex h-8 items-center gap-[7px] rounded-md border px-3 text-[12.5px] transition-colors disabled:opacity-50"
      :class="
        shared
          ? 'border-ok text-ok hover:bg-ok-soft'
          : 'border-line text-ink-2 hover:border-ink-4'
      "
      :disabled="shareBusy"
      @click="$emit('share')"
    >
      <svg
        class="h-3.5 w-3.5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path
          d="M4 12v7a1 1 0 001 1h14a1 1 0 001-1v-7M12 3v12M8 7l4-4 4 4"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      <span class="hidden lg:inline">
        {{ shared ? t('share.stopSharing') : t('share.shareButton') }}
      </span>
    </button>

    <div ref="menuRoot" class="relative">
      <button
        type="button"
        class="flex h-8 w-8 items-center justify-center rounded-md border border-line text-ink-2 transition-colors hover:border-ink-4"
        :aria-label="t('common.more')"
        @click="menuOpen = !menuOpen"
      >
        <svg
          class="h-[15px] w-[15px]"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.4"
          aria-hidden="true"
        >
          <circle cx="5" cy="12" r="1" />
          <circle cx="12" cy="12" r="1" />
          <circle cx="19" cy="12" r="1" />
        </svg>
      </button>

      <div
        v-if="menuOpen"
        class="absolute right-0 z-30 mt-1 min-w-[168px] rounded-md border border-line bg-panel py-1 shadow-soft-md"
      >
        <button
          type="button"
          class="flex w-full items-center px-3 py-1.5 text-left text-[12.5px] text-ink-2 transition-colors hover:bg-chip"
          @click="pick('share-settings')"
        >
          {{ t('share.modalTitle') }}
        </button>
        <button
          type="button"
          class="flex w-full items-center px-3 py-1.5 text-left text-[12.5px] text-bad transition-colors hover:bg-chip"
          @click="pick('delete')"
        >
          {{ t('common.delete') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

defineProps({
  busy: { type: Boolean, default: false },
  retrying: { type: Boolean, default: false },
  shared: { type: Boolean, default: false },
  shareBusy: { type: Boolean, default: false }
})

const emit = defineEmits(['retry', 'share', 'share-settings', 'delete'])

const { t } = useI18n()
const menuRoot = ref(null)
const menuOpen = ref(false)

const pick = (action) => {
  menuOpen.value = false
  emit(action)
}

const closeOnOutside = (event) => {
  if (
    menuOpen.value &&
    menuRoot.value &&
    !menuRoot.value.contains(event.target)
  ) {
    menuOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', closeOnOutside))
onBeforeUnmount(() => document.removeEventListener('click', closeOnOutside))
</script>
