<template>
  <div class="activity-grid">
    <section class="panel" aria-labelledby="overview-events-title">
      <header class="panel-head">
        <div>
          <h2 id="overview-events-title">
            需要你处理
            <span v-if="events.length" class="count">{{ events.length }}</span>
          </h2>
          <p>关注需要跟进的事件</p>
        </div>
        <button type="button" class="panel-link" @click="$emit('events')">
          全部事件 →
        </button>
      </header>
      <div v-if="events.length" class="event-list">
        <button
          v-for="event in events"
          :key="event.id"
          type="button"
          class="event-row"
          @click="$emit('open-event', event)"
        >
          <span class="event-mark" aria-hidden="true"></span>
          <strong>{{ event.title }}</strong>
          <span class="event-source">{{ eventSource(event) }}</span>
          <span class="tag" :class="event.status">{{
            eventStatusText(event.status)
          }}</span>
        </button>
      </div>
      <p v-else class="empty">
        {{ eventsAvailable ? '暂无已知状态的未完成事件' : '事件暂不可用' }}
      </p>
    </section>

    <section class="panel" aria-labelledby="overview-sync-title">
      <header class="panel-head">
        <div>
          <h2 id="overview-sync-title">最近同步</h2>
          <p>查看最近的上传与处理结果</p>
        </div>
        <button type="button" class="panel-link" @click="$emit('sync')">
          同步记录 →
        </button>
      </header>
      <div v-if="uploads.length" class="sync-list">
        <div
          v-for="upload in uploads.slice(0, 4)"
          :key="upload.id"
          class="sync-row"
        >
          <span class="sync-icon" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M20 7v5h-5M4 17v-5h5" />
              <path
                d="M5.3 9a7 7 0 0 1 11.3-2L20 12M4 12l3.4 5A7 7 0 0 0 19 15"
              />
            </svg>
          </span>
          <span class="sync-info">
            <strong>同步 #{{ upload.id }}</strong>
            <time>{{ formatDate(upload.created_at) || '时间未知' }}</time>
          </span>
          <span class="sync-count"
            >{{
              validCount(upload.message_count) ? upload.message_count : '未知'
            }}
            条消息</span
          >
          <span class="tag" :class="upload.status">{{
            uploadStatusText(upload.status)
          }}</span>
        </div>
      </div>
      <p v-else class="empty">
        {{ uploadsAvailable ? '暂无同步记录' : '同步记录暂不可用' }}
      </p>
      <div v-if="uploads.length" class="panel-foot">展示最近的同步记录</div>
    </section>
  </div>
</template>

<script setup>
import {
  eventSource,
  eventStatusText,
  formatDate,
  uploadStatusText,
  validCount
} from './formatters'

defineProps({
  events: { type: Array, required: true },
  eventsAvailable: { type: Boolean, required: true },
  uploads: { type: Array, required: true },
  uploadsAvailable: { type: Boolean, required: true }
})
defineEmits(['events', 'open-event', 'sync'])
</script>

<style scoped>
.activity-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr);
  gap: 16px;
  margin-top: 20px;
}
.panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid rgb(var(--c-line));
  border-radius: 14px;
  background: rgb(var(--c-panel));
  box-shadow: 0 4px 16px rgb(40 52 93 / 3%);
}
.panel-head {
  display: flex;
  min-height: 68px;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgb(var(--c-line-soft));
  padding: 12px 20px;
}
.panel-head h2 {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0;
  color: rgb(var(--c-tx));
  font-size: 15px;
  font-weight: 650;
}
.panel-head p {
  margin: 5px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.count {
  border-radius: 7px;
  background: rgb(var(--c-chip));
  padding: 3px 7px;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.panel-link {
  flex: none;
  margin-left: auto;
  color: rgb(var(--c-ac));
  font-size: 12px;
  font-weight: 600;
}
.event-row {
  display: flex;
  width: 100%;
  min-width: 0;
  min-height: 52px;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  text-align: left;
}
.event-row + .event-row,
.sync-row + .sync-row {
  border-top: 1px solid rgb(var(--c-line-soft));
}
.event-row:hover {
  background: rgb(var(--c-panel-sub));
}
.event-row:focus-visible,
.panel-link:focus-visible {
  outline: 2px solid rgb(var(--c-ac));
  outline-offset: -3px;
}
.event-mark {
  display: grid;
  width: 20px;
  height: 20px;
  flex: none;
  place-items: center;
  border: 2px solid rgb(var(--c-ac) / 30%);
  border-radius: 50%;
}
.event-mark::after {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgb(var(--c-ac) / 65%);
  content: '';
}
.event-row strong {
  min-width: 0;
  overflow: hidden;
  flex: 1;
  color: rgb(var(--c-tx));
  font-size: 13px;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-source {
  max-width: 32%;
  overflow: hidden;
  color: rgb(var(--c-tx3));
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag {
  flex: none;
  border-radius: 7px;
  background: rgb(var(--c-chip));
  padding: 5px 7px;
  color: rgb(var(--c-tx2));
  font-size: 11px;
  white-space: nowrap;
}
.tag.open,
.tag.pending,
.tag.created,
.tag.uploading {
  background: rgb(var(--c-warn-soft));
  color: rgb(var(--c-warn));
}
.tag.in_progress,
.tag.processing {
  background: rgb(var(--c-ac-soft));
  color: rgb(var(--c-ac));
}
.tag.completed,
.tag.done {
  background: rgb(var(--c-ok-soft));
  color: rgb(var(--c-ok));
}
.tag.failed,
.tag.cancelled {
  background: rgb(var(--c-bad-soft));
  color: rgb(var(--c-bad));
}
.sync-row {
  display: flex;
  min-width: 0;
  min-height: 52px;
  align-items: center;
  gap: 11px;
  padding: 8px 20px;
}
.sync-icon {
  display: grid;
  width: 30px;
  height: 30px;
  flex: none;
  place-items: center;
  border-radius: 9px;
  background: rgb(var(--c-ac-soft));
  color: rgb(var(--c-ac));
}
.sync-icon svg {
  width: 15px;
  height: 15px;
}
.sync-info {
  min-width: 0;
}
.sync-info strong {
  display: block;
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 12px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sync-info time {
  display: block;
  margin-top: 4px;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.sync-count {
  margin-left: auto;
  color: rgb(var(--c-tx3));
  font-size: 11px;
  white-space: nowrap;
}
.empty,
.panel-foot {
  margin: 0;
  padding: 20px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.panel-foot {
  min-height: 52px;
  border-top: 1px solid rgb(var(--c-line-soft));
  font-size: 11px;
}
@media (max-width: 1100px) {
  .activity-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 540px) {
  .panel-head,
  .event-row,
  .sync-row {
    padding-right: 15px;
    padding-left: 15px;
  }
  .event-source {
    display: none;
  }
  .sync-row {
    gap: 8px;
  }
}
</style>
