<template>
  <aside class="ev-drawer" role="complementary" aria-label="查看依据">
    <div class="ev-scrim" @click="emit('close')"></div>
    <div ref="panel" class="ev-panel" tabindex="-1">
      <header class="ev-head">
        <div class="ev-head-main">
          <span class="ev-kind">{{ kindLabel }}</span>
          <h2 class="ev-title">{{ title }}</h2>
          <p v-if="subtitle" class="ev-sub">{{ subtitle }}</p>
        </div>
        <button
          ref="closeButton"
          type="button"
          class="ev-close"
          aria-label="关闭依据"
          @click="emit('close')"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" />
          </svg>
        </button>
      </header>

      <div class="ev-body">
        <p v-if="loading" class="ev-hint" aria-busy="true">正在加载依据…</p>
        <p v-else-if="error" class="ev-hint bad" role="alert">{{ error }}</p>
        <EvidenceThread
          v-else-if="target.kind === 'message' && target.conversation_id"
          :space-id="spaceId"
          :conversation-id="target.conversation_id"
          :focus-message-id="target.id"
        />
        <p
          v-else-if="target.kind === 'message'"
          class="ev-hint bad"
          role="alert"
        >
          这条消息缺少所属会话，无法展示原文。
        </p>
        <EvidenceNotePreview
          v-else-if="note"
          :note="note"
          @navigate="emit('navigate', $event)"
        />
        <EvidenceEventPreview
          v-else-if="event"
          :event="event"
          :notes="eventNotes"
          @navigate="emit('navigate', $event)"
        />
      </div>

      <footer class="ev-foot">
        <span class="ev-foot-hint">{{ footHint }}</span>
        <button
          type="button"
          class="ev-btn"
          @click="emit('open-detail', target)"
        >
          {{ detailLabel }}
        </button>
      </footer>
    </div>
  </aside>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { spacesApi } from '@/api/spaces'
import EvidenceEventPreview from './EvidenceEventPreview.vue'
import EvidenceNotePreview from './EvidenceNotePreview.vue'
import EvidenceThread from './EvidenceThread.vue'

const props = defineProps({
  spaceId: { type: [String, Number], required: true },
  target: { type: Object, required: true }
})
const emit = defineEmits(['close', 'navigate', 'open-detail'])

const panel = ref(null)
const closeButton = ref(null)
const loading = ref(false)
const error = ref('')
const note = ref(null)
const event = ref(null)
const eventNotes = ref([])
const conversation = ref(null)
let requestId = 0

const unwrap = (response) => response.data?.data ?? response.data
const kindLabel = computed(
  () =>
    ({ message: '原始对话', note: '整理信息', event: '事件' })[
      props.target?.kind
    ] || '依据'
)
const title = computed(() => {
  if (props.target?.kind === 'message') {
    return (
      conversation.value?.title ||
      conversation.value?.source_conversation_id ||
      props.target?.title ||
      '原始对话'
    )
  }
  return (
    note.value?.title ||
    event.value?.title ||
    props.target?.title ||
    kindLabel.value
  )
})
const subtitle = computed(() => {
  if (props.target?.kind === 'message') return '引用消息已高亮'
  return ''
})
const footHint = computed(() =>
  props.target?.kind === 'message'
    ? '只读预览 · 展示引用消息前后的对话'
    : '只读预览 · 编辑请到详情页'
)
const detailLabel = computed(() =>
  props.target?.kind === 'message' ? '在会话中打开' : '打开详情'
)

async function load() {
  const target = props.target
  if (!target) return
  const current = ++requestId
  note.value = null
  event.value = null
  eventNotes.value = []
  conversation.value = null
  error.value = ''
  loading.value = false

  if (target.kind === 'message') {
    if (!target.conversation_id) return
    try {
      const data = unwrap(
        await spacesApi.getConversation(props.spaceId, target.conversation_id)
      )
      if (current === requestId) conversation.value = data
    } catch {
      /* the thread still renders without the conversation title */
    }
    return
  }

  loading.value = true
  try {
    if (target.kind === 'note') {
      note.value = unwrap(await spacesApi.getNote(target.id))
    } else if (target.kind === 'event') {
      const [eventResponse, notesResponse] = await Promise.all([
        spacesApi.getEvent(target.id),
        spacesApi.getEventNotes(target.id, { page_size: 20 })
      ])
      if (current !== requestId) return
      event.value = unwrap(eventResponse)
      eventNotes.value = unwrap(notesResponse).list || []
    }
  } catch (requestError) {
    if (current === requestId) {
      error.value =
        requestError.response?.data?.detail || '依据加载失败，请稍后重试。'
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
}

watch(() => props.target, load, { immediate: true })
onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  await nextTick()
  closeButton.value?.focus?.()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.ev-drawer {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  justify-content: flex-end;
}
.ev-scrim {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 41, 0.34);
}
.ev-panel {
  position: relative;
  z-index: 1;
  display: flex;
  width: min(620px, 100%);
  height: 100%;
  flex-direction: column;
  background: rgb(var(--c-panel));
  box-shadow: -18px 0 48px rgba(15, 23, 41, 0.18);
  outline: none;
}
.ev-head {
  display: flex;
  flex: none;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 14px 16px 12px;
}
.ev-head-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}
.ev-kind {
  color: rgb(var(--c-tx3));
  font-size: 11px;
  letter-spacing: 0.06em;
}
.ev-title {
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ev-sub {
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.ev-close {
  display: flex;
  width: 28px;
  height: 28px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: rgb(var(--c-tx3));
}
.ev-close:hover {
  background: rgb(var(--c-chip));
  color: rgb(var(--c-tx));
}
.ev-body {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow-y: auto;
  padding: 16px;
}
.ev-hint {
  margin: 0;
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
  line-height: 1.7;
}
.ev-hint.bad {
  color: rgb(var(--c-bad));
}
.ev-foot {
  display: flex;
  flex: none;
  align-items: center;
  gap: 12px;
  border-top: 1px solid rgb(var(--c-line-soft));
  padding: 10px 16px;
}
.ev-foot-hint {
  flex: 1;
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.ev-btn {
  flex: none;
  border-radius: 6px;
  background: rgb(var(--c-ac));
  padding: 6px 12px;
  color: rgb(var(--c-ac-on));
  font-size: 12px;
}
.ev-btn:hover {
  opacity: 0.9;
}

@media (min-width: 1536px) {
  .ev-drawer {
    position: static;
    z-index: auto;
    width: 560px;
    flex: none;
  }
  .ev-scrim {
    display: none;
  }
  .ev-panel {
    width: 100%;
    height: auto;
    min-height: 0;
    flex: 1;
    border-left: 1px solid rgb(var(--c-line));
    box-shadow: none;
  }
}
</style>
