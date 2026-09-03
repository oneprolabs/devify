<template>
  <section
    class="flex flex-col gap-2 rounded-lg border border-line bg-panel px-4 py-[13px]"
  >
    <div class="flex items-center gap-2">
      <span class="text-[12.5px] font-semibold text-ink">
        {{ t('chats.detail.mergedSources') }}
      </span>
      <span class="font-mono text-[10.5px] text-ink-3">
        {{ t('chats.mergedBadge', { count: children.length }) }}
      </span>
    </div>

    <div class="flex flex-col gap-[5px] font-mono text-[10.5px] text-ink-4">
      <span
        v-for="child in children"
        :key="child.uuid || child.id"
        :title="evidenceHint(child)"
      >
        {{ formatDate(child.received_at || child.created_at) }} ·
        {{ reasonLabel(child.merge_reason) }}
      </span>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  threadline: { type: Object, required: true },
  formatDate: { type: Function, required: true }
})

const { t } = useI18n()

const MERGE_REASONS = [
  'thread_relation',
  'forward_chain',
  'text_similarity',
  'manual'
]

const children = computed(() => props.threadline?.merged_children || [])

const reasonLabel = (reason) =>
  t(`chats.merge.reason.${MERGE_REASONS.includes(reason) ? reason : 'unknown'}`)

// Why the merger believed these belonged together; only useful on hover.
const evidenceHint = (child) => {
  const evidence = child.merge_evidence
  if (!evidence) return ''

  const parts = []
  if (evidence.signal && evidence.signal !== child.merge_reason) {
    parts.push(`via ${evidence.signal}`)
  }
  if (evidence.ratio != null) parts.push(`ratio ${evidence.ratio}`)
  if (evidence.partial_ratio != null) {
    parts.push(`partial ${evidence.partial_ratio}`)
  }
  if (evidence.matched_message_id) {
    parts.push(`message-id ${evidence.matched_message_id}`)
  }
  if (evidence.containment_score != null) {
    parts.push(`containment ${evidence.containment_score}`)
  }
  return parts.join(' · ')
}
</script>
