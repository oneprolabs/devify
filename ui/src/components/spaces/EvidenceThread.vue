<template>
  <div class="ev-thread">
    <p v-if="loading" class="ev-hint" aria-busy="true">正在读取对话…</p>
    <p v-else-if="error" class="ev-hint bad" role="alert">{{ error }}</p>
    <template v-else>
      <button
        v-if="hasEarlier"
        type="button"
        class="ev-more"
        :disabled="loadingMore"
        @click="loadEarlier"
      >
        {{ loadingMore ? '加载中…' : '加载更早的消息' }}
      </button>
      <p v-if="!messages.length" class="ev-hint">
        这个会话还没有已同步的消息。
      </p>
      <article
        v-for="message in messages"
        :id="`ev-msg-${message.id}`"
        :key="message.id"
        class="ev-msg"
        :class="{
          focus: isFocus(message),
          out: message.direction === 'outgoing'
        }"
      >
        <div class="ev-msg-meta">
          <span class="ev-sender">{{
            message.sender_name || message.sender_key || '未知发送者'
          }}</span>
          <time v-if="message.occurred_at" :datetime="message.occurred_at">
            {{ clock(message.occurred_at) }}
          </time>
          <span v-if="isFocus(message)" class="ev-flag">引用</span>
        </div>
        <div v-if="message.media?.length" class="ev-media">
          <template v-for="part in message.media" :key="part.id">
            <img
              v-if="part.kind === 'image' && mediaUrl(part)"
              :src="mediaUrl(part)"
              alt="图片"
              class="ev-image"
              loading="lazy"
            />
            <video
              v-else-if="part.kind === 'video' && mediaUrl(part)"
              :src="mediaUrl(part)"
              controls
              preload="metadata"
              class="ev-video"
            ></video>
            <audio
              v-else-if="part.kind === 'audio' && mediaUrl(part)"
              :src="mediaUrl(part)"
              controls
              class="ev-audio"
            ></audio>
            <a
              v-else-if="part.kind === 'file' && mediaUrl(part)"
              :href="mediaUrl(part)"
              target="_blank"
              rel="noreferrer"
              class="ev-file"
              >打开文件</a
            >
          </template>
        </div>
        <p v-if="bubbleText(message)" class="ev-bubble">
          {{ bubbleText(message) }}
        </p>
      </article>
    </template>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { spacesApi } from '@/api/spaces'
import { useChatMedia } from '@/composables/useChatMedia'

const props = defineProps({
  spaceId: { type: [String, Number], required: true },
  conversationId: { type: [String, Number], required: true },
  focusMessageId: { type: [String, Number], default: null }
})

const messages = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const page = ref(1)
const hasEarlier = ref(false)
let requestId = 0

const { resolve: resolveMedia } = useChatMedia()
const MEDIA_PLACEHOLDERS = /\[(图片|视频|语音|文件)\]/g
const mediaUrl = (part) => resolveMedia(part?.media_url)
// An image-only message previews as "[图片]"; drop the placeholder once the
// attachment itself is rendered, or the bubble says 图片 above the picture.
const bubbleText = (message) => {
  const text = message.preview || ''
  const hasMedia = (message.media || []).some((part) => part.media_url)
  if (!hasMedia) return text || '（无正文）'
  return text.replace(MEDIA_PLACEHOLDERS, '').trim()
}

const unwrap = (response) => response.data?.data ?? response.data
const clock = (value) =>
  new Date(value).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
const isFocus = (message) =>
  Boolean(props.focusMessageId) &&
  String(message.id) === String(props.focusMessageId)

// The drawer body is the scroll container, but it is laid out after the
// messages render; scroll once the frame is painted so the cited message
// lands in the middle instead of at the top of the list.
function scrollToFocus() {
  const target = messages.value.find((message) => isFocus(message))
  if (!target) return
  requestAnimationFrame(() => {
    const element = document.getElementById(`ev-msg-${target.id}`)
    if (!element) return
    let scroller = element.parentElement
    while (scroller) {
      const style = getComputedStyle(scroller)
      if (
        /(auto|scroll)/.test(style.overflowY) &&
        scroller.scrollHeight > scroller.clientHeight
      ) {
        break
      }
      scroller = scroller.parentElement
    }
    if (!scroller) return
    const scrollerBox = scroller.getBoundingClientRect()
    const elementBox = element.getBoundingClientRect()
    const delta = elementBox.top - scrollerBox.top
    scroller.scrollTop +=
      delta - scroller.clientHeight / 2 + elementBox.height / 2
  })
}

async function load() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  messages.value = []
  page.value = 1
  hasEarlier.value = false
  try {
    const params = { page_size: 100 }
    if (props.focusMessageId) params.focus_message_id = props.focusMessageId
    else params.page = 'last'
    const data = unwrap(
      await spacesApi.getMessages(props.spaceId, props.conversationId, params)
    )
    if (current !== requestId) return
    messages.value = data.list || []
    page.value = data.pagination?.page || 1
    hasEarlier.value = Boolean(data.pagination?.previous)
    await nextTick()
    scrollToFocus()
  } catch (requestError) {
    if (current === requestId) {
      error.value =
        requestError.response?.data?.detail || '对话加载失败，请稍后重试。'
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}

async function loadEarlier() {
  if (!hasEarlier.value || loadingMore.value) return
  loadingMore.value = true
  try {
    const data = unwrap(
      await spacesApi.getMessages(props.spaceId, props.conversationId, {
        page: Math.max(1, page.value - 1),
        page_size: 100
      })
    )
    messages.value = [...(data.list || []), ...messages.value]
    page.value = data.pagination?.page || Math.max(1, page.value - 1)
    hasEarlier.value = Boolean(data.pagination?.previous)
  } catch (requestError) {
    error.value =
      requestError.response?.data?.detail || '对话加载失败，请稍后重试。'
  } finally {
    loadingMore.value = false
  }
}

watch(() => [props.spaceId, props.conversationId, props.focusMessageId], load, {
  immediate: true
})
</script>

<style scoped>
.ev-thread {
  display: flex;
  flex-direction: column;
  gap: 10px;
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
.ev-more {
  align-self: center;
  border-radius: 6px;
  background: rgb(var(--c-chip));
  padding: 6px 12px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.ev-more:disabled {
  opacity: 0.6;
}
.ev-msg {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-left: 2px solid transparent;
  padding: 6px 10px;
}
.ev-msg.focus {
  border-left-color: rgb(var(--c-ac));
  border-radius: 0 8px 8px 0;
  background: rgb(var(--c-ac-soft));
}
.ev-msg-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.ev-msg-meta time {
  font-family: var(--font-mono);
}
.ev-sender {
  color: rgb(var(--c-tx2));
}
.ev-flag {
  border-radius: 4px;
  background: rgb(var(--c-ac));
  padding: 0 5px;
  color: rgb(var(--c-ac-on));
  font-size: 10.5px;
}
.ev-media {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ev-image {
  display: block;
  max-width: min(320px, 100%);
  max-height: 280px;
  border-radius: 8px;
  background: rgb(var(--c-chip));
  object-fit: contain;
}
.ev-video {
  display: block;
  max-width: min(320px, 100%);
  border-radius: 8px;
}
.ev-audio {
  width: min(320px, 100%);
}
.ev-file {
  color: rgb(var(--c-ac));
  font-size: 12.5px;
}
.ev-bubble {
  margin: 0;
  color: rgb(var(--c-tx));
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.ev-msg.out .ev-bubble {
  color: rgb(var(--c-tx2));
}
</style>
