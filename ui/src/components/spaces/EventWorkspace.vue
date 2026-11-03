<template>
  <div class="ws-page">
    <div class="ws-split" :class="{ 'mobile-open': mobileDetail }">
      <aside class="ws-rail" aria-labelledby="event-rail-title">
        <div class="ws-rail-head">
          <div class="ws-rail-top">
            <div class="ws-rail-title">
              <h1 id="event-rail-title">事件</h1>
              <span>{{ openCount }} 个未完成 · 跨全部会话</span>
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
              aria-label="搜索事件"
              placeholder="搜索事件"
            />
          </label>
          <div class="ws-seg" role="group" aria-label="事件状态筛选">
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
          <label v-if="tags.length" class="ws-filter-line">
            <span>标签</span>
            <select v-model="tagFilter" aria-label="按标签筛选">
              <option value="">全部</option>
              <option v-for="tag in tags" :key="tag.id" :value="tag.tag_key">
                {{ tag.label }}
              </option>
            </select>
          </label>
        </div>
        <div class="ws-rail-body">
          <div v-if="loading" class="ws-rail-hint" aria-busy="true">
            正在加载事件…
          </div>
          <div v-else-if="!filtered.length" class="ws-rail-hint">
            {{
              events.length
                ? '没有符合条件的事件。'
                : '还没有持续事件。整理信息被识别成事件后会出现在这里。'
            }}
          </div>
          <button
            v-for="event in filtered"
            v-else
            :key="event.id"
            type="button"
            class="ws-row"
            :class="{ on: selected?.id === event.id }"
            :aria-pressed="selected?.id === event.id"
            @click="choose(event)"
          >
            <span
              class="ws-ring"
              :class="ringClass(event)"
              style="margin-top: 3px"
            ></span>
            <span class="ws-row-main">
              <span class="ws-row-title">{{ event.title }}</span>
              <span class="ws-row-sub">{{ eventMeta(event) }}</span>
              <span v-if="event.tags?.length" class="ws-row-meta">
                <span v-for="tag in event.tags" :key="tag.id" class="ws-tag">{{
                  tag.label
                }}</span>
              </span>
              <span v-else-if="event.entity_key" class="ws-row-meta">
                <span class="ws-tag">{{ event.entity_key }}</span>
              </span>
            </span>
          </button>
          <button
            v-if="hasMore"
            type="button"
            class="ws-more"
            :disabled="loadingMore"
            @click="$emit('load-more')"
          >
            {{ loadingMore ? '加载中…' : '加载更多事件' }}
          </button>
          <p v-else-if="events.length > 100" class="ws-rail-hint">
            已加载全部事件。
          </p>
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
          <span class="ws-crumb">
            事件 / {{ selected ? statusLabel(selected.status) : '全部' }}
          </span>
          <div class="ws-det-actions">
            <router-link class="ws-btn ghost" :to="`/spaces/${spaceId}/chats`">
              查看原会话
            </router-link>
            <button
              v-if="canEdit && selected"
              type="button"
              class="ws-btn"
              @click="$emit('edit')"
            >
              编辑事件
            </button>
            <button
              v-if="canCreate"
              type="button"
              class="ws-btn primary"
              @click="$emit('create')"
            >
              新建事件
            </button>
          </div>
        </header>

        <div class="ws-det-body">
          <div v-if="detailLoading" class="ws-state" aria-busy="true">
            正在加载事件…
          </div>
          <div v-else-if="!selected" class="ws-state" role="status">
            <strong>选择一个事件</strong>
            <span>查看它当前的情况和变化记录。</span>
          </div>
          <div v-else class="ws-det-inner">
            <div class="ws-det-intro">
              <div class="ws-state-line">
                <span class="ws-ring" :class="ringClass(selected)"></span>
                <span>{{ statusLabel(selected.status) }}</span>
              </div>
              <h2 class="ws-display">{{ selected.title }}</h2>
              <div class="ws-meta-line">{{ metaLine(selected) }}</div>
            </div>

            <div class="ws-summary">
              {{ selected.content || '暂无情况描述' }}
            </div>

            <div v-if="canEdit" class="ws-tag-edit">
              <span
                v-for="tag in selected.tags || []"
                :key="tag.id"
                class="ws-tag ac"
              >
                {{ tag.label }}
                <button
                  type="button"
                  :aria-label="`移除标签 ${tag.label}`"
                  @click="removeTag(tag)"
                >
                  ×
                </button>
              </span>
              <select
                v-model="tagToAdd"
                aria-label="添加事件标签"
                @change="
                  addTag(
                    tags.find((item) => String(item.id) === String(tagToAdd))
                  )
                "
              >
                <option value="">添加标签</option>
                <option
                  v-for="tag in tags.filter(
                    (item) =>
                      !selected.tags?.some((current) => current.id === item.id)
                  )"
                  :key="tag.id"
                  :value="tag.id"
                >
                  {{ tag.label }}
                </option>
              </select>
              <button type="button" class="ws-link" @click="createTag">
                ＋ 新建标签
              </button>
            </div>

            <section class="ws-sect" aria-labelledby="event-timeline-title">
              <div class="ws-sectt">
                <span id="event-timeline-title">时间线</span>
                <span class="spacer"></span>
                <button
                  v-if="selected.note_ids?.length"
                  type="button"
                  class="ws-link"
                  @click="$emit('show-notes')"
                >
                  查看整理信息 ↗
                </button>
              </div>
              <p v-if="notesLoading" class="ws-note" aria-busy="true">
                正在加载关联信息…
              </p>
              <p v-else-if="notesError" class="ws-note" role="alert">
                关联信息加载失败，请刷新后重试。
              </p>
              <p v-else-if="!notes.length" class="ws-note">
                暂无关联的整理信息。
              </p>
              <div v-else class="ws-timeline">
                <article v-for="note in notes" :key="note.id" class="ws-tl">
                  <div class="ws-tl-time">
                    {{ formatShort(note.start_at || note.created_at) }}
                  </div>
                  <div class="ws-tl-rail">
                    <span class="ws-tl-dot"></span>
                    <span class="ws-tl-line"></span>
                  </div>
                  <div class="ws-tl-body">
                    <div class="ws-tl-top">
                      <span class="ws-tag">{{
                        note.origin === 'manual' ? '人工整理' : '整理信息'
                      }}</span>
                      <span>{{ note.title }}</span>
                    </div>
                    <div class="ws-tl-text">{{ note.content }}</div>
                    <details
                      v-if="note.evidence?.length"
                      class="ws-evidence-box"
                    >
                      <summary class="ws-tag">
                        原文 {{ note.evidence.length }} 条 →
                      </summary>
                      <div class="ws-evidence">
                        <button
                          v-for="(evidence, index) in note.evidence"
                          :key="evidence.id"
                          type="button"
                          class="ws-tag"
                          @click="openEvidence(evidence)"
                        >
                          第 {{ index + 1 }} 条
                          <template v-if="evidence.sender_name">
                            · {{ evidence.sender_name }}
                          </template>
                          →
                        </button>
                      </div>
                    </details>
                  </div>
                </article>
              </div>
              <button
                v-if="notesNext"
                type="button"
                class="ws-more"
                :disabled="notesLoadingMore"
                @click="loadMoreNotes"
              >
                {{ notesLoadingMore ? '加载中…' : '加载更多整理信息' }}
              </button>
            </section>

            <section
              v-if="selected.evidence?.length"
              class="ws-sect"
              aria-labelledby="event-evidence-title"
            >
              <div class="ws-sectt">
                <span id="event-evidence-title">原文证据</span>
                <span class="spacer"></span>
                <span class="ws-tag"
                  >{{ selected.evidence.length }} 条消息</span
                >
              </div>
              <div class="ws-evidence">
                <button
                  v-for="evidence in selected.evidence"
                  :key="evidence.id"
                  type="button"
                  class="ws-tag"
                  @click="openEvidence(evidence)"
                >
                  {{ formatShort(evidence.occurred_at) }}
                  <template v-if="evidence.sender_name">
                    · {{ evidence.sender_name }}
                  </template>
                  →
                </button>
              </div>
            </section>

            <div class="ws-clhint">
              <span class="ws-clmark">a</span>
              编辑事件、调整标签会立即同步到服务端；原始消息请到会话中查看。
            </div>
          </div>
        </div>

        <form
          v-if="selected && !detailLoading"
          class="ws-det-foot"
          @submit.prevent="ask"
        >
          <div class="ws-composer">
            <input
              v-model.trim="followup"
              type="text"
              placeholder="追问这件事，例如：客户最早什么时候提的？"
              aria-label="追问这件事"
            />
            <div class="ws-composer-foot">
              <span class="ws-tag ac"
                >范围：本事件 · {{ notes.length }} 条整理</span
              >
              <span class="spacer"></span>
              <span class="hint">回答会保存到「问答」</span>
              <button
                type="submit"
                class="ws-btn primary"
                :disabled="!followup"
              >
                追问
              </button>
            </div>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { spacesApi } from '@/api/spaces'

const props = defineProps({
  spaceId: { type: [String, Number], required: true },
  events: { type: Array, default: () => [] },
  selected: { type: Object, default: null },
  loading: Boolean,
  detailLoading: Boolean,
  canEdit: Boolean,
  canCreate: Boolean,
  hasMore: Boolean,
  loadingMore: Boolean
})
const emit = defineEmits([
  'select',
  'refresh',
  'show-notes',
  'edit',
  'create',
  'ask',
  'load-more',
  'select-citation'
])

const search = ref('')
const activeFilter = ref('all')
const mobileDetail = ref(false)
const tags = ref([])
const tagFilter = ref('')
const tagToAdd = ref('')
const followup = ref('')
const notes = ref([])
const notesLoading = ref(false)
const notesError = ref(false)
const notesNext = ref(false)
const notesLoadingMore = ref(false)
let requestId = 0

const openCount = computed(
  () => props.events.filter((item) => item.status !== 'done').length
)
const filters = computed(() => [
  { value: 'open', label: '未完成', count: openCount.value },
  {
    value: 'done',
    label: '已完成',
    count: props.events.length - openCount.value
  },
  { value: 'all', label: '全部', count: props.events.length }
])
const filtered = computed(() =>
  props.events.filter((item) => {
    const matchesFilter =
      activeFilter.value === 'all' ||
      (activeFilter.value === 'done'
        ? item.status === 'done'
        : item.status !== 'done')
    const matchesTag =
      !tagFilter.value ||
      item.tags?.some((tag) => tag.tag_key === tagFilter.value)
    const haystack = `${item.title} ${item.content || ''}`.toLowerCase()
    return (
      matchesFilter &&
      matchesTag &&
      haystack.includes(search.value.toLowerCase())
    )
  })
)
const statusLabel = (status) =>
  ({ open: '未完成', in_progress: '进行中', done: '已完成' })[status] ||
  '状态未设置'
const ringClass = (event) => {
  if (event.status === 'done') return 'done'
  return event.status === 'in_progress' ? 'rel' : ''
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
const formatShort = (value) =>
  value
    ? new Date(value).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    : '—'
const eventMeta = (event) => {
  const stamp = event.last_activity_at || event.opened_at
  return stamp
    ? `${statusLabel(event.status)} · ${formatShort(stamp)}`
    : statusLabel(event.status)
}
const metaLine = (event) => {
  const parts = []
  if (event.entity_key) parts.push(`实体 ${event.entity_key}`)
  if (event.opened_at) parts.push(`开始于 ${formatDate(event.opened_at)}`)
  if (event.last_activity_at)
    parts.push(`最近活动 ${formatDate(event.last_activity_at)}`)
  if (event.note_ids?.length) parts.push(`${event.note_ids.length} 条关联整理`)
  return parts.join(' · ')
}

function choose(event) {
  mobileDetail.value = true
  emit('select', event)
}
function ask() {
  if (!followup.value) return
  emit('ask', followup.value)
  followup.value = ''
}
function openEvidence(evidence) {
  emit('select-citation', {
    kind: 'message',
    id: evidence.message_id,
    conversation_id: evidence.conversation_id,
    title: evidence.sender_name || '原始消息',
    excerpt: evidence.reference_key
  })
}
async function loadMoreNotes() {
  if (!notesNext.value || notesLoadingMore.value || !props.selected?.id) return
  notesLoadingMore.value = true
  try {
    const response = await spacesApi.getEventNotes(props.selected.id, {
      page: Math.floor(notes.value.length / 100) + 1,
      page_size: 100
    })
    const data = response.data.data || response.data
    notes.value = [...notes.value, ...(data.list || [])]
    notesNext.value = Boolean(data.pagination?.next)
  } catch {
    notesError.value = true
  } finally {
    notesLoadingMore.value = false
  }
}
async function loadTags() {
  try {
    const response = await spacesApi.getEventTags(props.spaceId)
    tags.value = response.data.data || response.data || []
  } catch {
    tags.value = []
  }
}
async function createTag() {
  const label = window.prompt('标签名称')
  if (!label?.trim()) return
  try {
    const response = await spacesApi.createEventTag(props.spaceId, {
      label: label.trim()
    })
    const tag = response.data.data || response.data
    tags.value.push(tag)
    await addTag(tag)
  } catch {
    /* parent refresh will expose the error state */
  }
}
async function addTag(tag) {
  if (!props.selected?.id || !tag) return
  try {
    await spacesApi.addEventTag(props.selected.id, tag.id)
    emit('select', {
      ...props.selected,
      tags: [...(props.selected.tags || []), tag]
    })
    tagToAdd.value = ''
  } catch {
    /* keep the current tags */
  }
}
async function removeTag(tag) {
  if (!props.selected?.id) return
  try {
    await spacesApi.removeEventTag(props.selected.id, tag.id)
    emit('select', {
      ...props.selected,
      tags: (props.selected.tags || []).filter((item) => item.id !== tag.id)
    })
  } catch {
    /* keep the current tags */
  }
}

watch(
  () => [
    props.spaceId,
    props.selected?.id,
    props.selected?.note_ids,
    props.detailLoading
  ],
  async () => {
    const current = ++requestId
    notes.value = []
    notesError.value = false
    notesLoading.value = false
    followup.value = ''
    if (props.detailLoading || !props.selected?.note_ids?.length) return
    notesLoading.value = true
    try {
      const response = await spacesApi.getEventNotes(props.selected.id, {
        page_size: 100
      })
      const data = response.data.data || response.data
      if (current === requestId) {
        notes.value = data.list || []
        notesNext.value = Boolean(data.pagination?.next)
      }
    } catch {
      if (current === requestId) notesError.value = true
    } finally {
      if (current === requestId) notesLoading.value = false
    }
  },
  { immediate: true }
)
watch(
  () => props.spaceId,
  () => {
    search.value = ''
    activeFilter.value = 'all'
    tagFilter.value = ''
    mobileDetail.value = false
    loadTags()
  },
  { immediate: true }
)
</script>

<style scoped>
.ws-det-intro {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ws-tag-edit {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.ws-tag-edit .ws-tag button {
  margin-left: 3px;
  color: inherit;
}
.ws-tag-edit select {
  border: 1px solid rgb(var(--c-line));
  border-radius: 6px;
  background: rgb(var(--c-panel));
  padding: 4px 6px;
  color: rgb(var(--c-tx2));
  font-size: 11.5px;
}
.ws-link {
  color: rgb(var(--c-ac));
  font-size: 12.5px;
}
.ws-note {
  margin: 0;
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
  line-height: 1.7;
}
.ws-evidence {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}
.ws-evidence-box summary {
  display: inline-flex;
  list-style: none;
  cursor: pointer;
}
.ws-evidence-box summary::-webkit-details-marker {
  display: none;
}
.ws-tl-text {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
}
.ws-evidence .ws-tag {
  cursor: pointer;
}
.ws-det-foot {
  flex: none;
  border-top: 1px solid rgb(var(--c-line-soft));
  padding: 12px 32px 16px;
}
.ws-det-foot .ws-composer {
  max-width: 780px;
  margin: 0 auto;
  box-sizing: border-box;
}
</style>
