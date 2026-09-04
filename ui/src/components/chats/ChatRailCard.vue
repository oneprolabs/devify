<template>
  <!-- The list narrows to this while the drawer is open: enough to recognise
       a conversation and pick the next one, nothing more. -->
  <button
    type="button"
    class="flex w-full flex-col gap-[5px] border-b border-line-soft border-l-2 py-[11px] pr-3.5 text-left transition-colors"
    :class="
      active
        ? 'border-l-accent bg-accent-soft pl-3'
        : 'border-l-transparent pl-3.5 hover:bg-panel-sub'
    "
    :aria-current="active ? 'true' : undefined"
    @click="$emit('open', chat)"
  >
    <span class="flex items-center gap-[7px]">
      <ChatStatus :status="status" :percent="percent" compact />
      <span class="ml-auto flex-none font-mono text-[10px] text-ink-4">
        {{ time }}
      </span>
    </span>

    <span class="flex min-w-0 items-center gap-1.5">
      <span
        v-if="mergedCount"
        class="flex-none rounded-sm border border-accent px-1 py-px font-mono text-[9px] text-accent opacity-85"
      >
        {{ t('chats.mergedBadge', { count: mergedCount }) }}
      </span>
      <span class="truncate text-[12.5px] font-semibold text-ink">
        {{ title }}
      </span>
    </span>

    <span class="truncate text-[11px] text-ink-3">{{ preview }}</span>
  </button>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import ChatStatus from './ChatStatus.vue'
import { useChatRowFields } from '@/composables/useChatRowFields'

const props = defineProps({
  chat: { type: Object, required: true },
  active: { type: Boolean, default: false }
})

defineEmits(['open'])

const { t } = useI18n()

const { status, percent, title, preview, time, mergedCount } = useChatRowFields(
  () => props.chat
)
</script>
