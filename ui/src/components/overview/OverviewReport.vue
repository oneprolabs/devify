<template>
  <section class="report" aria-labelledby="overview-report-title">
    <div class="report-label">
      <h2 id="overview-report-title">最新报告</h2>
      <p>查看最近生成的报告</p>
    </div>
    <button
      v-if="report"
      type="button"
      class="report-content"
      @click="$emit('open')"
    >
      <span class="report-icon" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M6 3h8l4 4v14H6z" />
          <path d="M14 3v5h4M9 12h6M9 16h6" />
        </svg>
      </span>
      <span class="report-text">
        <span class="report-heading">
          <strong>{{ report.title || '未命名报告' }}</strong>
          <span class="type">报告</span>
          <time v-if="reportDate">{{ reportDate }} 生成</time>
        </span>
        <span class="report-preview">{{ preview }}</span>
      </span>
    </button>
    <p v-else class="empty">{{ available ? '还没有报告' : '报告暂不可用' }}</p>
    <button type="button" class="report-action" @click="$emit('open')">
      查看全部报告 →
    </button>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { formatDate } from './formatters'

const props = defineProps({
  report: { type: Object, default: null },
  available: { type: Boolean, required: true }
})
defineEmits(['open'])

const reportDate = computed(() =>
  formatDate(props.report?.generated_at || props.report?.created_at)
)
const preview = computed(() => {
  const body = props.report?.body
  if (typeof body !== 'string' || !body.trim()) return '暂无报告正文。'
  const text = body
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]*>/g, ' ')
    .replace(/^\s{0,3}(?:#{1,6}|>|[-*+]|\d+\.)\s+/gm, '')
    .replace(/[*_`~]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return '暂无报告正文。'
  return text.length > 240 ? `${text.slice(0, 240)}…` : text
})
</script>

<style scoped>
.report {
  display: grid;
  min-width: 0;
  grid-template-columns: 172px minmax(0, 1fr) auto;
  align-items: center;
  gap: 20px;
  min-height: 120px;
  margin-top: 16px;
  border: 1px solid rgb(var(--c-line));
  border-radius: 14px;
  background: rgb(var(--c-panel));
  padding: 19px 22px;
  box-shadow: 0 4px 16px rgb(40 52 93 / 3%);
}
.report-label {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-right: 1px solid rgb(var(--c-line-soft));
}
.report-label h2 {
  margin: 0;
  color: rgb(var(--c-tx));
  font-size: 15px;
  font-weight: 650;
}
.report-label p {
  margin: 7px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.report-content {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 13px;
  text-align: left;
}
.report-icon {
  display: grid;
  width: 38px;
  height: 42px;
  flex: none;
  place-items: center;
  border-radius: 9px;
  background: rgb(var(--c-ac-soft));
  color: rgb(var(--c-ac));
}
.report-icon svg {
  width: 19px;
  height: 19px;
}
.report-text {
  display: block;
  min-width: 0;
  flex: 1;
}
.report-heading {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
}
.report-heading strong {
  min-width: 0;
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.report-heading time {
  overflow: hidden;
  color: rgb(var(--c-tx3));
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.type {
  flex: none;
  border: 1px solid rgb(var(--c-line));
  border-radius: 5px;
  padding: 3px 6px;
  color: rgb(var(--c-tx3));
  font-size: 10px;
}
.report-preview {
  display: -webkit-box;
  overflow: hidden;
  margin-top: 8px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
  line-height: 1.6;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.empty {
  margin: 0;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.report-action {
  flex: none;
  border: 1px solid rgb(var(--c-line));
  border-radius: 8px;
  padding: 9px 13px;
  color: rgb(var(--c-ac));
  font-size: 12px;
  white-space: nowrap;
}
.report-action:hover,
.report-content:hover {
  color: rgb(var(--c-ac));
}
.report-action:focus-visible,
.report-content:focus-visible {
  outline: 2px solid rgb(var(--c-ac));
  outline-offset: 3px;
}
@media (max-width: 800px) {
  .report {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 14px;
  }
  .report-label {
    grid-column: 1 / -1;
    border-right: 0;
    border-bottom: 1px solid rgb(var(--c-line-soft));
    padding-bottom: 12px;
  }
}
@media (max-width: 540px) {
  .report {
    grid-template-columns: minmax(0, 1fr);
    padding: 17px;
  }
  .report-label {
    grid-column: auto;
  }
  .report-action {
    justify-self: start;
  }
  .report-heading time {
    display: none;
  }
}
</style>
