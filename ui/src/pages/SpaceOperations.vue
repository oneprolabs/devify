<template>
  <AppLayout :padded="false">
    <div class="ws-pg">
      <header class="ws-pghead">
        <h1 class="ws-pgtitle">同步记录</h1>
        <span class="ws-crumb"
          >各设备上传到云端的记录 · 定时与手动统一显示</span
        >
      </header>

      <div v-if="error" class="ws-alert" role="alert">{{ error }}</div>

      <div class="ws-pgbody">
        <div class="ws-wrap wide">
          <div class="sync-toolbar">
            <div class="ws-seg device-seg">
              <button
                v-for="option in deviceOptions"
                :key="option.value"
                type="button"
                :class="{ on: activeDevice === option.value }"
                @click="activeDevice = option.value"
              >
                {{ option.label }}
              </button>
            </div>
            <span class="spacer"></span>
            <span class="sync-hint"
              >定时上传 每 30 分钟 · 定时分析 09:00 / 21:00</span
            >
          </div>

          <div class="ws-listcard sync-table">
            <div class="sync-row sync-head" role="row">
              <span>任务</span>
              <span>开始</span>
              <span>设备</span>
              <span>方式</span>
              <span>内容</span>
              <span>结果</span>
              <span></span>
            </div>

            <div v-if="loading && !uploads.length" class="ws-state">
              正在读取同步记录…
            </div>
            <div v-else-if="!uploads.length" class="ws-state">
              <strong>还没有同步记录</strong>
              <span>在桌面客户端完成第一次上传后，记录会出现在这里。</span>
            </div>
            <div v-else-if="!visibleUploads.length" class="ws-state">
              <strong>这台设备还没有上传记录</strong>
              <span>切换到「全部设备」查看其他设备的同步。</span>
            </div>

            <template v-for="upload in visibleUploads" :key="upload.id">
              <button
                type="button"
                class="sync-row"
                :class="{ open: expanded === upload.id }"
                @click="toggle(upload)"
              >
                <span class="mono task">#{{ displayId(upload.id) }}</span>
                <time class="mono sync-time">{{
                  formatDate(upload.created_at)
                }}</time>
                <span class="device">{{ deviceName(upload) }}</span>
                <span class="mode">{{ modeText(upload) }}</span>
                <span class="content">{{ contentText(upload) }}</span>
                <span>
                  <span class="ws-tag" :class="statusInfo(upload).cls">{{
                    statusInfo(upload).text
                  }}</span>
                </span>
                <span class="chev">{{
                  expanded === upload.id ? '▾' : '▸'
                }}</span>
              </button>
              <div v-if="expanded === upload.id" class="stages">
                <div
                  v-for="stage in stagesFor(upload)"
                  :key="stage.label"
                  class="stage"
                >
                  <span class="stage-icon" :class="stage.tone">{{
                    stage.icon
                  }}</span>
                  <span class="stage-name">{{ stage.label }}</span>
                  <span class="stage-detail">{{ stage.detail }}</span>
                  <span class="mono stage-time">{{ stage.time }}</span>
                </div>
                <div v-if="upload.error_message" class="stage-foot">
                  <span class="stage-error" role="alert">{{
                    upload.error_message
                  }}</span>
                </div>
              </div>
            </template>
          </div>

          <button
            v-if="hasMore"
            type="button"
            class="ws-more"
            :disabled="loading"
            @click="load({ append: true })"
          >
            {{ loading ? '加载中…' : '加载更多' }}
          </button>

          <div class="ws-clhint">
            <span class="ws-clmark">a</span>
            手动上传、新建采集、修改上传周期在客户端「任务」中操作；失败的任务也由客户端自动重试。
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { authApi } from '@/api/auth'
import { spacesApi } from '@/api/spaces'

const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})

const uploads = ref([])
const devices = ref([])
const pagination = ref(null)
const page = ref(1)
const activeDevice = ref('all')
const expanded = ref(null)
const loading = ref(false)
const error = ref('')

const unwrap = (response) => response.data.data || response.data

const deviceById = computed(
  () => new Map(devices.value.map((device) => [device.device_id, device]))
)

const deviceOptions = computed(() => {
  const options = new Map()
  // Show every bound device, even before it has uploaded anything, so the
  // filter is stable instead of appearing only after the first sync.
  for (const device of devices.value) {
    if (!device.device_id) continue
    const label =
      device.label || `桌面客户端 · ${shortDeviceId(device.device_id)}`
    options.set(device.device_id, label.split(' · ')[0])
  }
  for (const upload of uploads.value) {
    if (upload.device_id && !options.has(upload.device_id)) {
      options.set(upload.device_id, `设备 ${shortDeviceId(upload.device_id)}`)
    }
  }
  if (
    uploads.value.some(
      (upload) => !upload.device_id && upload.source_provider === 'tauri_upload'
    )
  ) {
    options.set('__unknown_client__', '未记录设备')
  }
  return [
    { value: 'all', label: '全部设备' },
    ...[...options].map(([value, label]) => ({ value, label }))
  ]
})

const visibleUploads = computed(() => {
  if (activeDevice.value === 'all') return uploads.value
  if (activeDevice.value === '__unknown_client__') {
    return uploads.value.filter(
      (upload) => !upload.device_id && upload.source_provider === 'tauri_upload'
    )
  }
  return uploads.value.filter(
    (upload) => upload.device_id === activeDevice.value
  )
})

const hasMore = computed(() => Boolean(pagination.value?.next))

async function load({ append = false } = {}) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  const nextPage = append ? page.value + 1 : 1
  try {
    const response = await spacesApi.getUploads(props.spaceId, {
      page_size: 100,
      page: nextPage
    })
    const data = unwrap(response)
    const rows = Array.isArray(data) ? data : data.list || []
    uploads.value = append ? [...uploads.value, ...rows] : rows
    pagination.value = data.pagination || null
    page.value = nextPage
    if (!append) expanded.value = null
  } catch (requestError) {
    error.value =
      requestError.response?.data?.detail || '无法读取同步记录，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function loadDevices() {
  try {
    const response = await authApi.getDesktopDevices()
    const data = unwrap(response)
    devices.value = (Array.isArray(data) ? data : data.list || []).filter(
      (device) => device.status !== 'revoked'
    )
  } catch {
    // Device labels are an enhancement; the records still render without them.
    devices.value = []
  }
}

function toggle(upload) {
  expanded.value = expanded.value === upload.id ? null : upload.id
}

const displayId = (id) => String(id).padStart(4, '0')
const shortDeviceId = (id) => String(id || '').slice(0, 6)

const uploadPlatformText = (platform) => {
  const key = String(platform || '').toLowerCase()
  return (
    {
      macos: 'macOS',
      mac: 'macOS',
      darwin: 'macOS',
      windows: 'Windows',
      win: 'Windows',
      win32: 'Windows',
      linux: 'Linux'
    }[key] || ''
  )
}

const deviceName = (upload) => {
  if (!upload.device_id) {
    if (upload.source_provider === 'tauri_upload') {
      const platform = uploadPlatformText(upload.platform)
      return platform ? `桌面客户端 · ${platform}` : '桌面客户端 · 未记录设备'
    }
    return '网页导入'
  }
  const device = deviceById.value.get(upload.device_id)
  return device?.label || `设备 ${shortDeviceId(upload.device_id)}`
}

const modeText = (upload) =>
  ({ scheduled: '定时', manual: '手动' })[upload.trigger] ||
  (upload.device_id ? '客户端' : '网页')

const contentText = (upload) => {
  const conversations = Number(upload.conversation_count || 0)
  const messages = Number(upload.message_count || 0)
  if (!messages) return '0 条新消息'
  return `${conversations} 会话 · ${messages} 条`
}

const statusInfo = (upload) => {
  const status = upload.status
  if (status === 'created') return { text: '待上传', cls: '' }
  if (status === 'uploading') return { text: '上传中', cls: 'ac' }
  if (status === 'processing') return { text: '解析中', cls: 'ac' }
  if (status === 'failed') return { text: '失败', cls: 'bad' }
  if (status === 'cancelled') return { text: '已取消', cls: '' }
  const analysis = upload.analysis_summary
  if (!analysis || !analysis.job_count) {
    return Number(upload.message_count || 0) > 0
      ? { text: '已完成', cls: 'ok' }
      : { text: '无变化', cls: '' }
  }
  if (analysis.running) return { text: '关联分析中', cls: 'ac' }
  if (analysis.failed) return { text: '分析失败', cls: 'bad' }
  if (analysis.partial) return { text: '部分完成', cls: 'warn' }
  if (analysis.retried) return { text: '已重试成功', cls: 'ok' }
  if (analysis.event_count > 0) {
    return { text: `${analysis.event_count} 个事件`, cls: 'ok' }
  }
  return Number(upload.message_count || 0) > 0
    ? { text: '已完成', cls: 'ok' }
    : { text: '无变化', cls: '' }
}

const durationBetween = (start, end) => {
  if (!start || !end) return null
  const from = new Date(start).getTime()
  const to = new Date(end).getTime()
  if (Number.isNaN(from) || Number.isNaN(to) || to < from) return null
  return (to - from) / 1000
}

const formatDuration = (seconds) => {
  if (seconds === null || seconds === undefined) return ''
  const value = Math.max(0, Number(seconds))
  if (value < 0.1) return '<0.1s'
  if (value < 10) return `${value.toFixed(1)}s`
  if (value < 60) return `${Math.round(value)}s`
  const minutes = Math.floor(value / 60)
  const rest = Math.round(value % 60)
  return rest ? `${minutes}m ${rest}s` : `${minutes}m`
}

const stagesFor = (upload) => {
  const status = upload.status
  const completed = status === 'completed'
  const failed = status === 'failed'
  const cancelled = status === 'cancelled'
  const hasArchive =
    Boolean(upload.archive_received_at) ||
    ['processing', 'completed', 'failed'].includes(status)
  const clientUpload =
    Boolean(upload.device_id) || upload.source_provider === 'tauri_upload'
  const messages = Number(upload.message_count || 0)
  const conversations = Number(upload.conversation_count || 0)
  const images = Number(upload.image_count || 0)
  const duplicates = Number(upload.duplicate_count || 0)
  const analysis = upload.analysis_summary || {}
  const eventCount = Number(analysis.event_count || 0)
  const analysisDone = ['ready', 'partial'].includes(analysis.state)
  const analysisRunning = Boolean(analysis.running)
  const analysisFailed = Boolean(analysis.failed)
  return [
    {
      icon: clientUpload ? (hasArchive ? '✓' : '…') : '—',
      tone: hasArchive ? 'ok' : clientUpload ? 'ac' : 'muted',
      label: '打包',
      detail: clientUpload
        ? `${messages} 条消息 · ${conversations} 个会话 · ${images} 张图片（本机完成）`
        : `网页导入 · ${messages} 条消息 · ${conversations} 个会话`,
      time: ''
    },
    {
      icon: hasArchive ? '✓' : '…',
      tone: hasArchive ? 'ok' : 'ac',
      label: '上传',
      detail: hasArchive
        ? `归档 ${formatBytes(upload.archive_size)} 已送达云端`
        : '尚未收到归档',
      time: formatDuration(
        durationBetween(upload.created_at, upload.archive_received_at)
      )
    },
    {
      icon: completed ? '✓' : failed ? '!' : '…',
      tone: completed ? 'ok' : failed ? 'bad' : 'ac',
      label: '解析整理',
      detail: `会话 → 消息，归 ${messages} 条${
        duplicates ? ` · ${duplicates} 条重复` : ''
      }`,
      time: formatDuration(
        durationBetween(upload.parse_started_at, upload.completed_at)
      )
    },
    {
      icon: images ? (completed ? '✓' : '…') : '—',
      tone: images ? (completed ? 'ok' : 'ac') : 'muted',
      label: '图片处理',
      detail: images ? `${images} 张图片随消息保存` : '本次没有图片',
      time: ''
    },
    {
      icon: analysisDone ? '✓' : analysisFailed ? '!' : '…',
      tone: analysisDone ? 'ok' : analysisFailed ? 'bad' : 'ac',
      label: '事件识别',
      detail: analysisDone
        ? `识别出 ${eventCount} 个事件`
        : analysisRunning
          ? '正在识别事件'
          : analysisFailed
            ? '事件识别失败'
            : completed
              ? '已交给云端分析，等待事件识别'
              : cancelled
                ? '任务已取消，没有进入分析'
                : '等待解析完成',
      time: analysisDone ? formatDuration(analysis.duration_seconds) : ''
    },
    {
      icon: analysisDone ? '✓' : analysisRunning ? '…' : '…',
      tone: analysisDone ? 'ok' : 'ac',
      label: '关联分析',
      detail: analysisDone
        ? eventCount
          ? `已与已有事件合并，共 ${eventCount} 个事件`
          : '没有新事件需要关联'
        : analysisRunning
          ? '与历史事件比对中'
          : '等待事件识别',
      time: ''
    }
  ]
}

const formatDate = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  const time = date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
  if (sameDay) return `今天 ${time}`
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatBytes = (bytes) => {
  const value = Number(bytes || 0)
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  const digits = size >= 10 || index === 0 || Number.isInteger(size) ? 0 : 1
  return `${size.toFixed(digits)} ${units[index]}`
}

watch(
  () => props.spaceId,
  async () => {
    uploads.value = []
    pagination.value = null
    page.value = 1
    activeDevice.value = 'all'
    await Promise.all([load(), loadDevices()])
  }
)

onMounted(async () => {
  await Promise.all([load(), loadDevices()])
})
</script>

<style scoped>
.sync-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.sync-toolbar .spacer {
  flex: 1;
}
.device-seg {
  width: 340px;
  max-width: 100%;
}
.device-seg button {
  overflow: hidden;
  text-overflow: ellipsis;
}
.sync-hint {
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.sync-table {
  overflow: hidden;
}
.sync-row {
  display: grid;
  width: 100%;
  grid-template-columns:
    78px 128px minmax(0, 1.3fr) 56px minmax(0, 1fr)
    90px 20px;
  align-items: center;
  gap: 12px;
  padding: 11px 16px;
  color: rgb(var(--c-tx));
  font-size: 13px;
  text-align: left;
}
.sync-row:hover {
  background: rgb(var(--c-panel-sub));
}
.sync-row + .sync-row,
.stages + .sync-row {
  border-top: 1px solid rgb(var(--c-line-soft));
}
.sync-row.open {
  background: rgb(var(--c-panel-sub));
}
.sync-head {
  cursor: default;
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.sync-head:hover {
  background: transparent;
}
.task {
  color: rgb(var(--c-tx));
}
.sync-time {
  color: rgb(var(--c-tx2));
  font-size: 12.5px;
}
.device,
.mode,
.content {
  overflow: hidden;
  color: rgb(var(--c-tx2));
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chev {
  color: rgb(var(--c-tx3));
}
.stages {
  display: flex;
  flex-direction: column;
  border-top: 1px solid rgb(var(--c-line-soft));
  background: rgb(var(--c-panel-sub));
  padding: 8px 16px 12px 106px;
}
.stage {
  display: grid;
  grid-template-columns: 18px 110px minmax(0, 1fr) 50px;
  align-items: baseline;
  gap: 10px;
  padding: 7px 0;
  font-size: 12.5px;
}
.stage-icon {
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  text-align: center;
}
.stage-icon.ok {
  color: rgb(var(--c-ok));
}
.stage-icon.ac {
  color: rgb(var(--c-ac));
}
.stage-icon.bad {
  color: rgb(var(--c-bad));
}
.stage-name {
  color: rgb(var(--c-tx));
  font-weight: 500;
}
.stage-detail {
  min-width: 0;
  color: rgb(var(--c-tx2));
}
.stage-time {
  color: rgb(var(--c-tx3));
  text-align: right;
}
.stage-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding-top: 6px;
}
.stage-foot .mono {
  color: rgb(var(--c-tx3));
}
.stage-error {
  color: rgb(var(--c-bad));
  font-size: 12px;
  line-height: 1.6;
}
@media (max-width: 800px) {
  .sync-table {
    overflow-x: auto;
  }
  .sync-row {
    min-width: 680px;
  }
  .stages {
    padding-left: 16px;
  }
  .stage {
    grid-template-columns: 16px 90px minmax(0, 1fr);
  }
  .stage-time {
    display: none;
  }
}
</style>
