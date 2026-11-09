<template>
  <div class="ev-preview">
    <div class="ev-meta">
      <span class="ev-tag" :class="statusClass">{{ statusLabel }}</span>
      <span v-for="tag in event.tags || []" :key="tag.id" class="ev-tag ac">{{
        tag.label
      }}</span>
      <span v-if="event.last_activity_at">{{
        formatDate(event.last_activity_at)
      }}</span>
    </div>

    <p class="ev-text">{{ event.content || '暂无情况描述。' }}</p>

    <section class="ev-sect">
      <div class="ev-sectt">
        整理结论
        <span class="ev-count">{{ notes.length }}</span>
      </div>
      <p v-if="!notes.length" class="ev-hint">这个事件还没有关联的整理信息。</p>
      <div v-else class="ev-list">
        <button
          v-for="note in notes"
          :key="note.id"
          type="button"
          class="ev-row"
          @click="emit('navigate', { kind: 'note', id: note.id })"
        >
          <span class="ev-row-main">
            <span class="ev-row-title">{{ note.title }}</span>
            <span class="ev-row-sub">{{
              formatDate(note.start_at || note.created_at)
            }}</span>
          </span>
          <span class="ev-row-action">查看整理 →</span>
        </button>
      </div>
    </section>

    <section class="ev-sect">
      <div class="ev-sectt">
        原文证据
        <span class="ev-count">{{ event.evidence?.length || 0 }}</span>
      </div>
      <p v-if="!event.evidence?.length" class="ev-hint">
        这个事件还没有原文证据。
      </p>
      <div v-else class="ev-list">
        <button
          v-for="evidence in event.evidence"
          :key="evidence.id"
          type="button"
          class="ev-row"
          @click="openMessage(evidence)"
        >
          <span class="ev-row-main">
            <span class="ev-row-title">
              {{ formatDate(evidence.occurred_at) }}
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
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  event: { type: Object, required: true },
  notes: { type: Array, default: () => [] }
})
const emit = defineEmits(['navigate'])

const statusLabel = computed(
  () =>
    ({ open: '未完成', in_progress: '进行中', done: '已完成' })[
      props.event?.status
    ] || '状态未设置'
)
const statusClass = computed(() => {
  if (props.event?.status === 'done') return 'done'
  return props.event?.status === 'in_progress' ? 'rel' : ''
})
const formatDate = (value) =>
  value
    ? new Date(value).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    : '—'

function openMessage(evidence) {
  if (!evidence?.message_id) return
  emit('navigate', {
    kind: 'message',
    id: evidence.message_id,
    conversation_id: evidence.conversation_id,
    title: evidence.sender_name || '原始消息'
  })
}
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
.ev-tag.ac {
  background: rgb(var(--c-ac-soft));
  color: rgb(var(--c-ac));
}
.ev-tag.done {
  background: rgb(var(--c-ok-soft));
  color: rgb(var(--c-ok));
}
.ev-tag.rel {
  background: rgb(var(--c-warn-soft));
  color: rgb(var(--c-warn));
}
.ev-text {
  margin: 0;
  color: rgb(var(--c-tx));
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
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
