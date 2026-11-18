<template>
  <section
    class="rounded-lg border border-gray-200 bg-white p-5 min-w-0"
    aria-label="反馈详情"
    :inert="Boolean(activePreview)"
  >
    <header class="flex items-center justify-between gap-4 mb-4">
      <h2 class="font-semibold text-gray-900">反馈详情</h2>
      <button
        type="button"
        class="text-sm text-gray-500"
        @click="$emit('close')"
      >
        关闭详情
      </button>
    </header>
    <p class="text-xs text-gray-500 break-all">
      {{ report.id }} · {{ report.submitted_by }}
    </p>
    <p class="whitespace-pre-wrap break-words my-4 text-sm">
      {{ report.description }}
    </p>
    <p v-if="report.contact" class="text-sm mb-4">
      联系方式：{{ report.contact }}
    </p>

    <div v-if="attachments.length" class="mb-4">
      <p class="text-xs text-gray-500 mb-2">截图（点击查看大图）</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button
          v-for="(item, index) in attachments"
          :key="item.id"
          type="button"
          class="group relative flex h-40 items-center justify-center overflow-hidden rounded border border-gray-200 bg-gray-50 disabled:cursor-default"
          :disabled="item.expired"
          :aria-label="`查看截图 ${index + 1}`"
          @click="onThumbnailClick(index)"
        >
          <img
            v-if="previews[item.id]?.url"
            :src="previews[item.id].url"
            :alt="`反馈截图 ${index + 1}`"
            class="h-full w-full object-contain transition group-hover:scale-[1.02]"
          />
          <span
            v-else-if="item.expired"
            class="px-3 text-center text-xs text-gray-500"
          >
            附件已过期
          </span>
          <span
            v-else-if="previews[item.id]?.error"
            class="px-3 text-center text-xs text-red-600"
            role="alert"
          >
            {{ previews[item.id].error }}
          </span>
          <span v-else class="text-xs text-gray-400">加载中…</span>
          <span
            v-if="previews[item.id]?.url"
            class="pointer-events-none absolute bottom-2 right-2 rounded bg-black/60 px-2 py-1 text-xs text-white opacity-0 transition group-hover:opacity-100"
          >
            查看大图
          </span>
        </button>
      </div>
      <p v-if="attachmentError" role="alert" class="mt-2 text-sm text-red-600">
        {{ attachmentError }}
      </p>
    </div>

    <details class="text-sm mb-4">
      <summary class="cursor-pointer text-gray-600">环境与诊断信息</summary>
      <pre
        class="mt-2 p-3 bg-gray-50 rounded overflow-auto max-h-64 text-xs whitespace-pre-wrap break-all"
        >{{ JSON.stringify(report.context, null, 2) }}</pre
      >
      <pre
        v-if="diagnosticsText"
        class="mt-2 p-3 bg-gray-50 rounded overflow-auto max-h-64 text-xs whitespace-pre-wrap break-all"
        >{{ diagnosticsText }}</pre
      >
    </details>
    <form
      class="space-y-4 border-t border-gray-100 pt-4"
      @submit.prevent="save"
    >
      <label class="block text-sm"
        >处理状态<select
          v-model="form.status"
          class="mt-1 w-full border border-gray-300 rounded px-3 py-2"
        >
          <option value="received">已收到</option>
          <option value="processing">处理中</option>
          <option value="needs_info">待补充</option>
          <option value="resolved">已解决</option>
        </select></label
      >
      <label class="block text-sm"
        >处理人用户 ID（选填）<input
          v-model="assignee"
          type="number"
          min="1"
          class="mt-1 w-full border border-gray-300 rounded px-3 py-2"
          placeholder="管理员用户 ID"
      /></label>
      <label class="block text-sm"
        >回复用户<textarea
          v-model="form.reply"
          rows="4"
          maxlength="5000"
          class="mt-1 w-full border border-gray-300 rounded px-3 py-2"
          placeholder="说明处理进展或需要补充的信息"
        />
      </label>
      <label class="block text-sm"
        >修复版本<input
          v-model="form.fix_version"
          maxlength="64"
          class="mt-1 w-full border border-gray-300 rounded px-3 py-2"
          placeholder="例如 0.1.1"
      /></label>
      <p v-if="error" role="alert" class="text-sm text-red-600">
        {{ error }}
      </p>
      <p v-if="saved" role="status" class="text-sm text-green-700">
        处理结果已保存，用户可在客户端查看。
      </p>
      <button
        type="submit"
        :disabled="busy"
        class="px-4 py-2 rounded bg-primary-600 text-white text-sm disabled:opacity-50"
      >
        {{ busy ? '保存中…' : '保存处理结果' }}
      </button>
    </form>
  </section>

  <div
    v-if="activePreview"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
    role="dialog"
    aria-modal="true"
    aria-label="截图预览"
    @click.self="closePreview"
  >
    <div class="flex max-h-full w-full max-w-5xl flex-col">
      <div class="flex items-center justify-between mb-3 text-sm text-white">
        <span>截图 {{ activeIndex + 1 }} / {{ attachments.length }}</span>
        <div class="flex items-center gap-2">
          <a
            v-if="activePreview.url"
            :href="activePreview.url"
            target="_blank"
            rel="noopener"
            class="rounded border border-white/40 px-3 py-1.5 hover:bg-white/10"
            >新标签页打开</a
          >
          <button
            type="button"
            class="rounded border border-white/40 px-3 py-1.5 hover:bg-white/10"
            @click="download(activePreview.item)"
          >
            下载
          </button>
          <button
            ref="closeButton"
            type="button"
            class="rounded bg-white/15 px-3 py-1.5 hover:bg-white/25"
            @click="closePreview"
          >
            关闭
          </button>
        </div>
      </div>
      <img
        v-if="activePreview.url"
        :src="activePreview.url"
        :alt="`反馈截图 ${activeIndex + 1}`"
        class="max-h-[80vh] w-full rounded bg-white object-contain"
      />
      <p
        v-if="activePreview.error"
        class="rounded bg-white p-6 text-sm text-red-600"
      >
        {{ activePreview.error }}
      </p>
      <p
        v-if="attachmentError"
        role="alert"
        class="mt-3 rounded bg-white p-3 text-sm text-red-600"
      >
        {{ attachmentError }}
      </p>
    </div>
  </div>
</template>

<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch
} from 'vue'
import { feedbackApi } from '@/admin/api/feedback'
import { extractErrorMessage } from '@/utils/api'

const props = defineProps({ report: { type: Object, required: true } })
const emit = defineEmits(['close', 'updated'])
const form = reactive({ status: '', reply: '', fix_version: '' })
const assignee = ref('')
const busy = ref(false)
const saved = ref(false)
const error = ref('')
const attachmentError = ref('')
const previews = reactive({})
const activeIndex = ref(-1)
const closeButton = ref(null)
let previousFocus = null
let loadToken = 0
let disposed = false

const attachments = computed(() => props.report.attachments || [])

// Version 2 diagnostics are already one greppable line per record; older
// reports keep the structured JSON so nothing becomes unreadable.
const diagnosticsText = computed(() => {
  const diagnostics = props.report.diagnostics
  if (!diagnostics) return ''
  if (Array.isArray(diagnostics.lines)) return diagnostics.lines.join('\n')
  return JSON.stringify(diagnostics, null, 2)
})

const activePreview = computed(() => {
  if (activeIndex.value < 0) return null
  const item = attachments.value[activeIndex.value]
  if (!item) return null
  return { item, ...(previews[item.id] || {}) }
})

watch(
  () => props.report,
  (report) => {
    Object.assign(form, {
      status: report.status,
      reply: report.reply,
      fix_version: report.fix_version
    })
    assignee.value = report.assigned_to || ''
    error.value = ''
    saved.value = false
  },
  { immediate: true }
)

// Selecting another report reuses this component, so drop the previous
// object URLs and refetch instead of showing screenshots of the old report.
watch(
  () => props.report.id,
  (id, previousId) => {
    if (previousId === undefined || id === previousId) return
    loadPreviews()
  }
)

watch(activeIndex, async (index) => {
  if (index >= 0) {
    // Capture the trigger before the render patch marks the page inert.
    previousFocus = document.activeElement
    await nextTick()
    closeButton.value?.focus()
  } else if (previousFocus) {
    const target = previousFocus
    previousFocus = null
    // Wait for `inert` to be removed, otherwise focus() is a no-op.
    await nextTick()
    target.focus?.()
  }
})

function saveBlob(blob, id) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `screenshot-${id}.png`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function releasePreviews() {
  loadToken += 1
  Object.values(previews).forEach((preview) => {
    if (preview?.url) URL.revokeObjectURL(preview.url)
  })
  Object.keys(previews).forEach((id) => delete previews[id])
  activeIndex.value = -1
  attachmentError.value = ''
}

async function loadPreview(item, token) {
  try {
    const blob = await feedbackApi.fetchAttachment(item)
    if (disposed || token !== loadToken) return
    previews[item.id] = {
      url: URL.createObjectURL(blob),
      blob,
      loading: false,
      error: ''
    }
  } catch (err) {
    if (disposed || token !== loadToken) return
    previews[item.id] = {
      url: '',
      blob: null,
      loading: false,
      error: extractErrorMessage(err, '预览加载失败。')
    }
  }
}

async function loadPreviews() {
  releasePreviews()
  const token = loadToken
  const pending = attachments.value.filter((item) => !item.expired)
  // Every pending attachment starts in "loading" so the grid never shows an
  // error for a thumbnail that simply has not been fetched yet.
  pending.forEach((item) => {
    previews[item.id] = { url: '', blob: null, loading: true, error: '' }
  })
  for (const item of pending) {
    if (disposed || token !== loadToken) break
    await loadPreview(item, token)
  }
}

function onThumbnailClick(index) {
  const item = attachments.value[index]
  if (!item || item.expired) return
  const preview = previews[item.id]
  if (preview?.url) {
    activeIndex.value = index
    return
  }
  if (preview?.loading) return
  previews[item.id] = { url: '', blob: null, loading: true, error: '' }
  loadPreview(item, loadToken)
}

function closePreview() {
  activeIndex.value = -1
}

function handleKeydown(event) {
  if (event.key === 'Escape' && activeIndex.value >= 0) closePreview()
}

async function download(item) {
  attachmentError.value = ''
  try {
    const cached = previews[item.id]
    if (cached?.blob) {
      saveBlob(cached.blob, item.id)
      return
    }
    const blob = await feedbackApi.fetchAttachment(item)
    saveBlob(blob, item.id)
  } catch (err) {
    attachmentError.value = extractErrorMessage(err, '下载失败，请重试。')
  }
}

async function save() {
  busy.value = true
  error.value = ''
  saved.value = false
  try {
    const report = await feedbackApi.update(props.report.id, {
      ...form,
      assigned_to: assignee.value ? Number(assignee.value) : null
    })
    emit('updated', report)
    saved.value = true
  } catch (err) {
    error.value = extractErrorMessage(err, '保存失败，请重试。')
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  disposed = false
  window.addEventListener('keydown', handleKeydown)
  loadPreviews()
})

onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('keydown', handleKeydown)
  releasePreviews()
})
</script>
