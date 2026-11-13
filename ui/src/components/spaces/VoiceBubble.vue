<template>
  <div class="voice-wrap">
    <button
      type="button"
      class="voice-bubble"
      :class="{ outgoing }"
      :aria-label="playing ? '暂停语音' : '播放语音'"
      :disabled="loading"
      @click="toggle"
    >
      <svg
        class="voice-icon"
        :class="{ playing }"
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M4 10v4h3l4 3V7l-4 3H4z" />
        <path class="voice-wave-inner" d="M14 9a4 4 0 0 1 0 6" />
        <path class="voice-wave-outer" d="M17 6a8 8 0 0 1 0 12" />
      </svg>
      <span v-if="loading" class="voice-loading">加载中…</span>
      <span v-if="duration" class="voice-duration">{{ duration }}″</span>
    </button>
    <audio
      ref="audio"
      preload="metadata"
      @ended="playing = false"
      @pause="playing = false"
      @loadedmetadata="readDuration"
      @error="onError"
    />
    <span v-if="error" class="voice-error" role="status">{{ error }}</span>
  </div>
</template>

<script setup>
import { onUnmounted, ref } from 'vue'
import api from '@/api'

const props = defineProps({
  url: { type: String, required: true },
  outgoing: Boolean
})
const audio = ref(null)
const loading = ref(false)
const playing = ref(false)
const duration = ref(0)
const error = ref('')
let objectUrl = ''
let disposed = false

async function toggle() {
  if (playing.value) {
    audio.value.pause()
    playing.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    if (!objectUrl) {
      const response = await api.get(props.url, { responseType: 'blob' })
      if (disposed) return
      objectUrl = URL.createObjectURL(response.data)
      audio.value.src = objectUrl
    }
    await audio.value.play()
    if (!disposed) playing.value = true
  } catch {
    if (!disposed) error.value = '语音加载失败，请重试'
  } finally {
    if (!disposed) loading.value = false
  }
}
function readDuration() {
  if (Number.isFinite(audio.value?.duration))
    duration.value = Math.max(1, Math.round(audio.value.duration))
}
function onError() {
  error.value = '语音播放失败，请重试'
  playing.value = false
}
onUnmounted(() => {
  disposed = true
  if (objectUrl) URL.revokeObjectURL(objectUrl)
})
</script>

<style scoped>
.voice-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}
.voice-bubble {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  position: relative;
  min-width: 112px;
  min-height: 48px;
  padding: 10px 16px;
  border: 0;
  border-radius: 9px;
  background: #ededee;
  color: rgb(var(--c-tx));
  cursor: pointer;
}
.voice-bubble::before {
  content: '';
  position: absolute;
  left: -5px;
  top: 19px;
  width: 10px;
  height: 10px;
  background: inherit;
  transform: rotate(45deg);
}
.voice-bubble.outgoing {
  background: #d9f3de;
}
.voice-bubble.outgoing::before {
  left: auto;
  right: -5px;
}
.voice-icon {
  width: 22px;
  height: 22px;
  flex: none;
}
.voice-icon.playing .voice-wave-inner {
  animation: voice-wave 1s steps(1, end) infinite;
}
.voice-icon.playing .voice-wave-outer {
  animation: voice-wave 1s steps(1, end) infinite 0.3s;
}
@keyframes voice-wave {
  0%,
  30% {
    opacity: 0;
  }
  31%,
  100% {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .voice-icon.playing .voice-wave-inner,
  .voice-icon.playing .voice-wave-outer {
    animation: none;
  }
  .voice-icon.playing {
    opacity: 0.55;
  }
}
.voice-duration {
  font-size: 16px;
}
.voice-loading {
  font-size: 12px;
  color: rgb(var(--c-tx2));
}
.voice-error {
  color: #b94451;
  font-size: 12px;
}
audio {
  display: none;
}
</style>
