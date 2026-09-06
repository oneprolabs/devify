<template>
  <div
    class="flex h-[45px] flex-shrink-0 items-center justify-between border-t border-line bg-panel-sub px-4 md:px-5"
  >
    <span class="font-mono text-[calc(11px*var(--fs))] text-ink-3">
      {{ t('chats.showingRange', { from, to, total }) }}
    </span>
    <div class="flex items-center gap-1.5">
      <button
        type="button"
        class="rounded-md border border-line px-[11px] py-[5px] font-mono text-[calc(11px*var(--fs))] transition-colors"
        :class="
          page > 1
            ? 'text-ink hover:border-ink-4'
            : 'cursor-not-allowed text-ink-4'
        "
        :disabled="page <= 1"
        @click="$emit('update:page', page - 1)"
      >
        {{ t('chats.prevPage') }}
      </button>
      <button
        type="button"
        class="rounded-md border border-line px-[11px] py-[5px] font-mono text-[calc(11px*var(--fs))] transition-colors"
        :class="
          hasMore
            ? 'text-ink hover:border-ink-4'
            : 'cursor-not-allowed text-ink-4'
        "
        :disabled="!hasMore"
        @click="$emit('update:page', page + 1)"
      >
        {{ t('chats.nextPage') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  total: { type: Number, required: true },
  count: { type: Number, required: true },
  hasMore: { type: Boolean, default: false }
})

defineEmits(['update:page'])

const { t } = useI18n()

const from = computed(() =>
  props.count ? (props.page - 1) * props.pageSize + 1 : 0
)
const to = computed(() => (props.page - 1) * props.pageSize + props.count)
</script>
