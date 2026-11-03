<template>
  <div class="ws-page">
    <div class="ws-split" :class="{ 'mobile-open': mobileDetail }">
      <aside class="ws-rail" aria-labelledby="report-rail-title">
        <div class="ws-rail-head">
          <div class="ws-rail-top">
            <div class="ws-rail-title">
              <h1 id="report-rail-title">报告</h1>
              <span>{{ reports.length }} 份 · 服务端按计划生成</span>
            </div>
            <button
              v-if="canCreate"
              type="button"
              class="ws-rail-action"
              @click="$emit('create')"
            >
              ＋ 新建
            </button>
          </div>
          <div class="ws-seg" role="group" aria-label="报告状态筛选">
            <button
              v-for="filter in filters"
              :key="filter.value"
              type="button"
              :class="{ on: activeFilter === filter.value }"
              :aria-pressed="activeFilter === filter.value"
              @click="activeFilter = filter.value"
            >
              {{ filter.label }}<span>{{ filter.count }}</span>
            </button>
          </div>
        </div>
        <div class="ws-rail-body">
          <div v-if="loading" class="ws-rail-hint" aria-busy="true">
            正在加载报告…
          </div>
          <div v-else-if="!filtered.length" class="ws-rail-hint">
            {{
              reports.length
                ? '没有符合状态的报告。'
                : '还没有报告。主题订阅生成报告后会出现在这里。'
            }}
          </div>
          <button
            v-for="report in filtered"
            v-else
            :key="report.id"
            type="button"
            class="ws-row"
            :class="{ on: selected?.id === report.id }"
            :aria-pressed="selected?.id === report.id"
            @click="choose(report)"
          >
            <span class="ws-rk">{{ reportMark(report) }}</span>
            <span class="ws-row-main">
              <span class="ws-row-title">{{
                report.title || '未命名报告'
              }}</span>
              <span class="ws-row-sub">{{ reportMeta(report) }}</span>
            </span>
          </button>
        </div>
      </aside>

      <section class="ws-det" aria-live="polite">
        <header class="ws-det-head">
          <button
            type="button"
            class="ws-mobile-back"
            @click="mobileDetail = false"
          >
            ← 返回
          </button>
          <span class="ws-crumb"> 报告 / {{ selected?.title || '全部' }} </span>
          <div class="ws-det-actions">
            <button
              type="button"
              class="ws-btn ghost"
              :disabled="loading"
              @click="$emit('refresh')"
            >
              刷新
            </button>
            <button
              v-if="canCreate"
              type="button"
              class="ws-btn primary"
              @click="$emit('create')"
            >
              新建报告
            </button>
          </div>
        </header>

        <div class="ws-det-body">
          <div v-if="detailLoading" class="ws-state" aria-busy="true">
            正在加载报告…
          </div>
          <div v-else-if="!selected" class="ws-state" role="status">
            <strong>选择一份报告</strong>
            <span>查看报告正文和它引用的条目。</span>
          </div>
          <div v-else class="ws-det-inner wide">
            <div class="ws-report-head">
              <span class="ws-rk strong">{{ reportMark(selected) }}</span>
              <div class="ws-report-head-copy">
                <h2 class="ws-display">{{ selected.title || '未命名报告' }}</h2>
                <div class="ws-meta-line">{{ reportMeta(selected) }}</div>
                <p
                  v-if="selected.status === 'failed'"
                  class="ws-note"
                  role="alert"
                >
                  报告生成失败，可以重新生成。
                </p>
                <p
                  v-else-if="selected.status === 'partial'"
                  class="ws-note"
                  role="status"
                >
                  报告生成未完全完成，下面展示的是已保存的快照。
                </p>
              </div>
            </div>

            <div class="ws-soft report-soft">
              <span v-if="periodRange(selected)" class="ws-mono">{{
                periodRange(selected)
              }}</span>
              <div v-if="selected.body" class="report-body">
                {{ selected.body }}
              </div>
              <div v-else class="ws-note">这份报告还没有正文。</div>
              <div class="ws-report-nums">
                {{ sectionCount }} 个分组 · {{ itemCount }} 条记录
              </div>
            </div>

            <section
              v-for="section in selected.sections || []"
              :key="section.id"
              class="ws-sect"
            >
              <div class="ws-sectt">
                {{ section.title || '未命名分组' }}
                <span class="n">{{ section.items?.length || 0 }}</span>
              </div>
              <div class="ws-listcard">
                <div
                  v-for="item in section.items || []"
                  :key="item.id"
                  class="ws-li report-item"
                >
                  <div class="ws-li-main">
                    <span class="ws-li-title">{{ item.title }}</span>
                    <span v-if="item.summary" class="ws-li-sub">{{
                      item.summary
                    }}</span>
                  </div>
                  <button
                    v-for="source in citableSources(item)"
                    :key="source.id"
                    type="button"
                    class="ws-li-action"
                    @click="openSource(source)"
                  >
                    查看依据 →
                  </button>
                </div>
              </div>
            </section>

            <div v-if="!selected.sections?.length" class="ws-clhint">
              <span class="ws-clmark">a</span>
              这份报告只有正文，没有分组条目。报告由服务端任务生成；需要重新生成时请到「主题订阅」立即生成。
            </div>
            <div v-else class="ws-note">
              报告条目来自事件与整理信息，点击「查看依据」可以回到对应内容。
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  spaceId: { type: [String, Number], required: true },
  reports: { type: Array, default: () => [] },
  selected: { type: Object, default: null },
  loading: Boolean,
  detailLoading: Boolean,
  canCreate: Boolean
})
const emit = defineEmits(['select', 'refresh', 'create', 'open-citation'])

const activeFilter = ref('all')
const mobileDetail = ref(false)

const statusLabel = (status) =>
  ({
    queued: '生成中',
    ready: '已生成',
    partial: '部分完成',
    failed: '失败'
  })[status] || '状态未设置'
const markFor = (report) =>
  String(report.title || '')
    .trim()
    .charAt(0) || '报'
const reportMark = (report) => markFor(report)
const periodLabel = (value) => {
  if (!value) return ''
  const date = new Date(value)
  return `${String(date.getMonth() + 1).padStart(2, '0')}/${String(
    date.getDate()
  ).padStart(2, '0')}`
}
const periodRange = (report) => {
  if (!report.period_start && !report.period_end) return ''
  const start = periodLabel(report.period_start)
  const end = periodLabel(report.period_end)
  if (start && end) return `${start} – ${end}`
  return start || end
}
const reportMeta = (report) => {
  const range = periodRange(report)
  return [range, statusLabel(report.status)].filter(Boolean).join(' · ')
}
const matchesStatus = {
  ready: (report) => report.status === 'ready' || report.status === 'partial',
  queued: (report) => report.status === 'queued',
  failed: (report) => report.status === 'failed'
}
const filters = computed(() => [
  { value: 'all', label: '全部', count: props.reports.length },
  {
    value: 'ready',
    label: '已生成',
    count: props.reports.filter(matchesStatus.ready).length
  },
  {
    value: 'queued',
    label: '生成中',
    count: props.reports.filter(matchesStatus.queued).length
  },
  {
    value: 'failed',
    label: '失败',
    count: props.reports.filter(matchesStatus.failed).length
  }
])
const filtered = computed(() =>
  activeFilter.value === 'all'
    ? props.reports
    : props.reports.filter(matchesStatus[activeFilter.value])
)
const sectionCount = computed(() => props.selected?.sections?.length || 0)
const itemCount = computed(() =>
  (props.selected?.sections || []).reduce(
    (total, section) => total + (section.items?.length || 0),
    0
  )
)

function choose(report) {
  mobileDetail.value = true
  emit('select', report)
}
function citableSources(item) {
  return (item.sources || []).filter(
    (source) => source.event_id || source.note_id
  )
}
function openSource(source) {
  emit('open-citation', {
    kind: source.source_kind === 'note' ? 'note' : 'event',
    id: source.event_id || source.note_id,
    title: source.display_text || ''
  })
}
</script>

<style scoped>
.ws-report-head {
  display: flex;
  align-items: center;
  gap: 14px;
}
.ws-report-head-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}
.ws-rk.strong {
  width: 44px;
  height: 44px;
  background: rgb(var(--c-tx));
  color: rgb(var(--c-bg));
  font-size: 18px;
}
.report-soft {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.report-body {
  white-space: pre-wrap;
  color: rgb(var(--c-tx2));
  font-size: 14px;
  line-height: 1.85;
}
.ws-report-nums {
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  font-size: 12px;
}
.report-item {
  align-items: flex-start;
}
.report-item .ws-li-main {
  gap: 4px;
}
.report-item .ws-li-sub {
  white-space: normal;
  line-height: 1.7;
}
.ws-note {
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
  line-height: 1.7;
}
</style>
