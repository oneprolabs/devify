<template>
  <div class="ev-preview">
    <div class="ev-meta">
      <span class="ev-tag">{{ originLabel }}</span>
      <span v-if="note.start_at || note.created_at">{{
        formatDate(note.start_at || note.created_at)
      }}</span>
    </div>

    <p class="ev-text" :class="{ clamped: !expanded && isLong }">
      {{ note.content || '这条整理没有正文。' }}
    </p>
    <button
      v-if="isLong"
      type="button"
      class="ev-link"
      @click="expanded = !expanded"
    >
      {{ expanded ? '收起全文' : '展开全文' }}
    </button>

    <section class="ev-sect">
      <div class="ev-sectt">
        原文证据
        <span class="ev-count">{{ note.evidence?.length || 0 }}</span>
      </div>
      <p v-if="!note.evidence?.length" class="ev-hint">
        这条整理还没有原文证据。
      </p>
      <div v-else class="ev-list">
        <button
          v-for="evidence in note.evidence"
          :key="evidence.id"
          type="button"
          class="ev-row"
          @click="openMessage(evidence)"
        >
          <span class="ev-row-main">
            <span class="ev-row-title">
              #{{ evidence.message_id }}
              <template v-if="evidence.sender_name">
                · {{ evidence.sender_name }}
              </template>
            </span>
            <span class="ev-row-sub">{{
              evidence.reference_key || '原始消息'
            }}</span>
          </span>
          <span class="ev-row-action">查看原文 →</span>
        </button>
      </div>
    </section>

    <section class="ev-sect">
      <div class="ev-sectt">
        关联事件
        <span class="ev-count">{{ note.event_ids?.length || 0 }}</span>
      </div>
      <p v-if="!note.event_ids?.length" class="ev-hint">
        这条整理还没有关联事件。
      </p>
      <div v-else class="ev-list">
        <button
          v-for="eventId in note.event_ids"
          :key="eventId"
          type="button"
          class="ev-row"
          @click="emit('navigate', { kind: 'event', id: eventId })"
        >
          <span class="ev-row-main">
            <span class="ev-row-title">事件 #{{ eventId }}</span>
          </span>
          <span class="ev-row-action">查看事件 →</span>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  note: { type: Object, required: true }
})
const emit = defineEmits(['navigate'])

const expanded = ref(false)
const isLong = computed(() => (props.note?.content || '').length > 600)
const originLabel = computed(() =>
  props.note?.origin === 'manual' ? '人工整理' : '自动整理'
)
const formatDate = (value) =>
  value
    ? new Date(value).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    : ''

function openMessage(evidence) {
  if (!evidence?.message_id) return
  emit('navigate', {
    kind: 'message',
    id: evidence.message_id,
    conversation_id: evidence.conversation_id,
    title: evidence.sender_name || '原始消息'
  })
}

watch(
  () => props.note?.id,
  () => {
    expanded.value = false
  }
)
</script>

<style scoped>
.ev-preview {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.ev-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.ev-tag {
  border-radius: 4px;
  background: rgb(var(--c-chip));
  padding: 1px 6px;
  color: rgb(var(--c-tx2));
}
.ev-text {
  margin: 0;
  color: rgb(var(--c-tx));
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
.ev-text.clamped {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 12;
}
.ev-link {
  align-self: flex-start;
  color: rgb(var(--c-ac));
  font-size: 12.5px;
}
.ev-sect {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ev-sectt {
  display: flex;
  align-items: baseline;
  gap: 6px;
  color: rgb(var(--c-tx2));
  font-size: 12.5px;
  font-weight: 600;
}
.ev-count {
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 400;
}
.ev-hint {
  margin: 0;
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
}
.ev-list {
  overflow: hidden;
  border: 1px solid rgb(var(--c-line));
  border-radius: 8px;
}
.ev-row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  text-align: left;
}
.ev-row + .ev-row {
  border-top: 1px solid rgb(var(--c-line-soft));
}
.ev-row:hover {
  background: rgb(var(--c-panel-sub));
}
.ev-row-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}
.ev-row-title {
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ev-row-sub {
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.ev-row-action {
  flex: none;
  color: rgb(var(--c-ac));
  font-size: 12px;
}
</style>
