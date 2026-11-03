<template>
  <div class="ws-page">
    <div class="ws-split" :class="{ 'mobile-open': mobileDetail }">
      <aside class="ws-rail" aria-labelledby="note-rail-title">
        <div class="ws-rail-head">
          <div class="ws-rail-top">
            <div class="ws-rail-title">
              <h1 id="note-rail-title">整理</h1>
              <span>{{ notes.length }} 条 · 来自会话与事件</span>
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
          <label class="ws-rail-search">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="6.5" />
              <path d="M16 16l4 4" stroke-linecap="round" />
            </svg>
            <input
              v-model.trim="search"
              type="search"
              aria-label="搜索整理信息"
              placeholder="搜索整理信息"
            />
          </label>
          <div class="ws-rail-top">
            <button
              type="button"
              class="ws-rail-action"
              @click="$emit('back-events')"
            >
              ← 事件
            </button>
          </div>
        </div>
        <div class="ws-rail-body">
          <div v-if="loading" class="ws-rail-hint" aria-busy="true">
            正在加载整理信息…
          </div>
          <div v-else-if="!filtered.length" class="ws-rail-hint">
            {{ notes.length ? '没有符合条件的整理信息。' : '还没有整理信息。' }}
          </div>
          <button
            v-for="note in filtered"
            v-else
            :key="note.id"
            type="button"
            class="ws-row"
            :class="{ on: selected?.id === note.id }"
            :aria-pressed="selected?.id === note.id"
            @click="choose(note)"
          >
            <span class="ws-row-main">
              <span class="ws-row-title">{{ note.title }}</span>
              <span class="ws-row-sub">{{ noteMeta(note) }}</span>
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
          <span class="ws-crumb">整理 / {{ selected?.title || '全部' }}</span>
          <div class="ws-det-actions">
            <button
              v-if="canEdit && selected"
              type="button"
              class="ws-btn ghost"
              @click="$emit('edit')"
            >
              编辑
            </button>
            <button
              v-if="canCreate"
              type="button"
              class="ws-btn primary"
              @click="$emit('create')"
            >
              新建整理
            </button>
          </div>
        </header>

        <div class="ws-det-body">
          <div v-if="detailLoading" class="ws-state" aria-busy="true">
            正在加载整理信息…
          </div>
          <div v-else-if="!selected" class="ws-state" role="status">
            <strong>选择一条整理信息</strong>
            <span>查看它的内容、原文证据和关联事件。</span>
          </div>
          <div v-else class="ws-det-inner">
            <div class="ws-det-intro">
              <div class="ws-state-line">
                <span
                  v-for="tag in noteTags(selected)"
                  :key="tag"
                  class="ws-tag"
                  >{{ tag }}</span
                >
              </div>
              <h2 class="ws-display">{{ selected.title }}</h2>
              <div class="ws-meta-line">{{ noteMeta(selected) }}</div>
            </div>

            <div class="ws-soft note-content">
              {{ displayContent }}
            </div>
            <button
              v-if="hasLongContent"
              type="button"
              class="ws-link note-toggle"
              @click="expanded = !expanded"
            >
              {{ expanded ? '收起全文' : '展开全文' }}
            </button>

            <section class="ws-sect">
              <div class="ws-sectt">
                原文证据
                <span class="n">{{ selected.evidence?.length || 0 }}</span>
              </div>
              <div v-if="!selected.evidence?.length" class="ws-note">
                这条整理还没有原文证据。
              </div>
              <div v-else class="ws-listcard">
                <div
                  v-for="evidence in selected.evidence"
                  :key="evidence.id"
                  class="ws-li"
                >
                  <div class="ws-li-main">
                    <span class="ws-li-title">
                      #{{ evidence.message_id }}
                      <template v-if="evidence.sender_name">
                        · {{ evidence.sender_name }}
                      </template>
                    </span>
                    <span class="ws-li-sub">{{
                      evidence.reference_key || '原始消息'
                    }}</span>
                  </div>
                  <button
                    type="button"
                    class="ws-li-action"
                    @click="openMessage(evidence)"
                  >
                    查看原文 →
                  </button>
                </div>
              </div>
            </section>

            <section class="ws-sect">
              <div class="ws-sectt">
                关联事件
                <span class="n">{{ selected.event_ids?.length || 0 }}</span>
              </div>
              <div v-if="!selected.event_ids?.length" class="ws-note">
                这条整理还没有关联事件。
              </div>
              <div v-else class="ws-listcard">
                <button
                  v-for="eventId in selected.event_ids"
                  :key="eventId"
                  type="button"
                  class="ws-li"
                  @click="$emit('open-event', eventId)"
                >
                  <span class="ws-li-main">
                    <span class="ws-li-title">事件 #{{ eventId }}</span>
                  </span>
                  <span class="ws-li-action">查看事件 →</span>
                </button>
              </div>
            </section>

            <form
              v-if="canEdit"
              class="ws-listcard evidence-form"
              @submit.prevent="submitEvidence"
            >
              <label>
                <span>添加原文证据</span>
                <input
                  v-model="evidenceMessageId"
                  inputmode="numeric"
                  placeholder="消息 ID"
                />
              </label>
              <button
                type="submit"
                class="ws-btn"
                :disabled="!evidenceMessageId"
              >
                添加
              </button>
            </form>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  spaceId: { type: [String, Number], required: true },
  notes: { type: Array, default: () => [] },
  selected: { type: Object, default: null },
  loading: Boolean,
  detailLoading: Boolean,
  canCreate: Boolean,
  canEdit: Boolean
})
const emit = defineEmits([
  'select',
  'create',
  'edit',
  'add-evidence',
  'open-event',
  'open-message',
  'back-events'
])

const search = ref('')
const mobileDetail = ref(false)
const evidenceMessageId = ref('')
const expanded = ref(false)

const hasLongContent = computed(
  () => (props.selected?.content || '').length > 480
)
const displayContent = computed(() => {
  const text = props.selected?.content || ''
  if (!expanded.value && text.length > 480) return `${text.slice(0, 480)}…`
  return text
})

const filtered = computed(() =>
  props.notes.filter((note) =>
    `${note.title} ${note.content || ''}`
      .toLowerCase()
      .includes(search.value.toLowerCase())
  )
)
const originLabel = (origin) =>
  ({
    auto: '自动整理',
    manual: '人工整理',
    assigned: '已指派',
    unassigned: '未指派'
  })[origin] || '手动'
const noteTags = (note) => {
  const tags = [originLabel(note.origin)]
  if (note.assignment_mode === 'manual') tags.push('手动归属')
  return tags.filter(Boolean)
}
const formatDate = (value) =>
  value
    ? new Date(value).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    : ''
const noteMeta = (note) =>
  [originLabel(note.origin), formatDate(note.start_at || note.created_at)]
    .filter(Boolean)
    .join(' · ')

function choose(note) {
  mobileDetail.value = true
  evidenceMessageId.value = ''
  expanded.value = false
  emit('select', note)
}
function openMessage(evidence) {
  emit('open-message', {
    kind: 'message',
    id: evidence.message_id,
    conversation_id: evidence.conversation_id,
    title: evidence.sender_name || '原始消息',
    excerpt: evidence.reference_key
  })
}
function submitEvidence() {
  if (!evidenceMessageId.value) return
  emit('add-evidence', Number(evidenceMessageId.value))
  evidenceMessageId.value = ''
}
watch(
  () => props.selected?.id,
  () => {
    expanded.value = false
  }
)
</script>

<style scoped>
.ws-det-intro {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ws-note {
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
  line-height: 1.7;
}
.note-toggle {
  align-self: flex-start;
  margin-top: -14px;
  color: rgb(var(--c-ac));
  font-size: 12.5px;
}
.evidence-form {
  flex-direction: row;
  align-items: flex-end;
  gap: 10px;
  padding: 12px 15px;
}
.evidence-form label {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.evidence-form input {
  width: 100%;
  border: 1px solid rgb(var(--c-line));
  border-radius: 6px;
  background: rgb(var(--c-panel));
  padding: 7px 8px;
  color: rgb(var(--c-tx));
  font-size: 12.5px;
}
</style>
