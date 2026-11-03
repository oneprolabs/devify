<template>
  <AppLayout :padded="false">
    <div class="settings">
      <header class="settings-head">
        <div class="settings-title">
          <h1>设备与设置</h1>
          <p>查看已绑定的客户端、空间处理默认值与云端数据用量。</p>
        </div>
        <button
          type="button"
          class="refresh-button"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? '加载中…' : '刷新' }}
        </button>
      </header>

      <div v-if="error" class="page-alert" role="alert">{{ error }}</div>

      <div class="settings-body">
        <div class="wrap">
          <section class="sect">
            <div class="sh">
              <h2>
                已绑定设备
                <span v-if="!loading" class="sh-count">{{
                  devices.length
                }}</span>
              </h2>
              <p>在客户端登录这个账号即自动绑定；解除绑定后需要重新登录。</p>
            </div>
            <div class="listcard">
              <div v-if="loading && !devices.length" class="state">
                正在加载设备…
              </div>
              <div v-else-if="!devices.length" class="state">
                <strong>还没有绑定设备</strong>
                <span>在桌面客户端登录后，设备会出现在这里。</span>
              </div>
              <template v-else>
                <div
                  v-for="device in devices"
                  :key="device.device_id"
                  class="device-row"
                >
                  <div class="device-copy">
                    <div class="device-title">
                      <strong>{{ deviceName(device) }}</strong>
                      <span class="dot" :class="stateClass(device)"></span>
                      <span class="device-state">{{ stateText(device) }}</span>
                    </div>
                    <div class="device-meta">
                      <span>绑定于 {{ formatDay(device.created_at) }}</span>
                      <span
                        >最近活跃
                        {{ formatRelative(device.last_seen_at) }}</span
                      >
                      <span v-if="shortId(device)" class="mono">{{
                        shortId(device)
                      }}</span>
                    </div>
                  </div>
                  <span class="device-platform mono">{{
                    platformText(device.platform)
                  }}</span>
                  <button
                    type="button"
                    class="revoke-button"
                    :disabled="revoking === device.device_id"
                    @click="revoke(device)"
                  >
                    {{ revoking === device.device_id ? '解除中…' : '解除绑定' }}
                  </button>
                </div>
              </template>
            </div>
          </section>

          <section class="sect">
            <div class="sh">
              <h2>采集与分析</h2>
              <p>
                这个空间的处理默认值保存在服务端，客户端上传与云端分析都按它执行。
              </p>
            </div>
            <div class="listcard">
              <div v-if="!workflow" class="state">
                {{
                  loading ? '正在加载处理默认值…' : '暂时无法读取处理默认值。'
                }}
              </div>
              <template v-else>
                <div v-for="row in analysisRows" :key="row.label" class="kv">
                  <span class="k">{{ row.label }}</span>
                  <span class="v">{{ row.value }}</span>
                  <span class="hint">{{ row.hint }}</span>
                </div>
              </template>
            </div>
          </section>

          <section class="sect">
            <div class="sh">
              <h2>云端数据</h2>
              <p>
                云端保存解析后的会话、消息与识别结果；本机数据由客户端自行管理。
              </p>
            </div>
            <div class="listcard">
              <div v-if="!usage" class="state">
                {{ loading ? '正在加载云端用量…' : '暂时无法读取云端用量。' }}
              </div>
              <template v-else>
                <div class="kv">
                  <span class="k">已用空间</span>
                  <span class="cloud-value">
                    <span class="mono">{{
                      formatBytes(usage.storage_used_bytes)
                    }}</span>
                    <span class="cloud-sub">
                      {{ number(usage.conversation_count) }} 个会话 ·
                      {{ number(usage.message_count) }} 条消息 ·
                      {{ number(usage.media_count) }} 个媒体文件
                    </span>
                  </span>
                  <span class="hint">{{ storageLimitHint }}</span>
                </div>
                <div class="kv">
                  <span class="k">成员</span>
                  <span>{{ number(usage.member_count) }} 人</span>
                  <span class="hint">{{ memberLimitHint }}</span>
                </div>
                <div class="kv">
                  <span class="k">今日 AI 调用</span>
                  <span>{{ number(usage.daily_ai_calls_used) }} 次</span>
                  <span class="hint">{{ aiCallLimitHint }}</span>
                </div>
              </template>
            </div>
          </section>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { authApi } from '@/api/auth'
import { spacesApi } from '@/api/spaces'

const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})

const devices = ref([])
const workflow = ref(null)
const usage = ref(null)
const quota = ref(null)
const loading = ref(false)
const revoking = ref('')
const error = ref('')

const unwrap = (response) => response.data.data || response.data

const analysisRows = computed(() => {
  const config = workflow.value
  if (!config) return []
  return [
    {
      label: '自动处理',
      value: config.processing_paused
        ? '已暂停'
        : config.auto_process
          ? '开启'
          : '手动触发',
      hint: config.processing_paused
        ? '新上传的数据会等待手动恢复'
        : '上传完成后自动解析与分析'
    },
    {
      label: '附件策略',
      value: attachmentText(config.attachment_policy),
      hint: '媒体文件与附件如何随消息处理'
    },
    {
      label: '语言',
      value: languageText(config.language),
      hint: '摘要与识别结果使用的语言'
    },
    {
      label: '分析场景',
      value: sceneText(config.scene),
      hint: '默认的提示词与分析口径'
    },
    {
      label: '配置版本',
      value: `v${config.version}`,
      hint: config.updated_at
        ? `更新于 ${formatDate(config.updated_at)}`
        : '尚未修改过'
    }
  ]
})

const storageLimit = computed(() => quota.value?.storage_limit_bytes ?? null)
const memberLimit = computed(() => quota.value?.max_members ?? null)
const dailyAiLimit = computed(() => quota.value?.daily_ai_calls ?? null)

const storageLimitHint = computed(() =>
  storageLimit.value === null
    ? '未设置上限'
    : `上限 ${formatBytes(storageLimit.value)}`
)
const memberLimitHint = computed(() =>
  memberLimit.value === null ? '未设置上限' : `上限 ${memberLimit.value} 人`
)
const aiCallLimitHint = computed(() =>
  dailyAiLimit.value === null ? '未设置上限' : `上限 ${dailyAiLimit.value} 次`
)

async function load() {
  loading.value = true
  error.value = ''
  const [deviceResult, configResult, usageResult] = await Promise.allSettled([
    authApi.getDesktopDevices(),
    spacesApi.getWorkflowConfig(props.spaceId),
    spacesApi.getQuotaUsage(props.spaceId)
  ])
  const failures = []
  if (deviceResult.status === 'fulfilled') {
    const data = unwrap(deviceResult.value)
    devices.value = (Array.isArray(data) ? data : data.list || []).filter(
      (device) => device.status !== 'revoked'
    )
  } else {
    failures.push('设备列表')
  }
  if (configResult.status === 'fulfilled') {
    workflow.value = unwrap(configResult.value)
  } else {
    failures.push('处理默认值')
  }
  if (usageResult.status === 'fulfilled') {
    const data = unwrap(usageResult.value)
    usage.value = data.usage || null
    quota.value = data.quota || null
  } else {
    failures.push('云端用量')
  }
  if (failures.length) {
    error.value = `无法读取${failures.join('、')}，请稍后重试。`
  }
  loading.value = false
}

async function revoke(device) {
  if (revoking.value) return
  const name = deviceName(device)
  if (!window.confirm(`确定解除“${name}”的绑定？该设备需要重新登录。`)) {
    return
  }
  revoking.value = device.device_id
  error.value = ''
  try {
    await authApi.revokeDesktopDevice(device.device_id)
    devices.value = devices.value.filter(
      (item) => item.device_id !== device.device_id
    )
  } catch (requestError) {
    error.value =
      requestError.response?.data?.detail || '解除绑定失败，请稍后重试。'
  } finally {
    revoking.value = ''
  }
}

const deviceName = (device) =>
  device.label || `桌面客户端 · ${String(device.device_id).slice(0, 6)}`
const shortId = (device) =>
  device.label ? String(device.device_id).slice(0, 8) : ''
const platformText = (platform) => {
  const key = String(platform || '').toLowerCase()
  if (!key) return '平台未上报'
  return (
    {
      macos: 'macOS',
      mac: 'macOS',
      darwin: 'macOS',
      windows: 'Windows',
      win: 'Windows',
      win32: 'Windows',
      linux: 'Linux',
      ios: 'iOS',
      android: 'Android'
    }[key] || platform
  )
}
const minutesSince = (value) => {
  if (!value) return null
  const time = new Date(value).getTime()
  if (Number.isNaN(time)) return null
  return Math.max(0, Math.round((Date.now() - time) / 60000))
}
const stateClass = (device) => {
  const minutes = minutesSince(device.last_seen_at)
  return minutes !== null && minutes < 10 ? 'online' : 'offline'
}
const stateText = (device) => {
  const minutes = minutesSince(device.last_seen_at)
  if (minutes === null) return '离线'
  return minutes < 10 ? '在线' : '离线'
}
const formatRelative = (value) => {
  const minutes = minutesSince(value)
  if (minutes === null) return '未知'
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days === 1) return '昨天'
  if (days < 30) return `${days} 天前`
  return formatDay(value)
}
const formatDay = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit'
  })
}
const formatDate = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
const formatBytes = (bytes) => {
  const value = Number(bytes || 0)
  if (!value) return '0 KB'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  const digits = size >= 10 || index === 0 ? 0 : 1
  return `${size.toFixed(digits)} ${units[index]}`
}
const number = (value) => Number(value || 0).toLocaleString('zh-CN')
const attachmentText = (policy) =>
  ({
    available: '保留可用附件',
    skip: '跳过附件',
    required: '需要附件'
  })[policy] ||
  policy ||
  '—'
const languageText = (language) =>
  ({
    'zh-CN': '简体中文',
    'en-US': 'English',
    es: 'Español'
  })[language] ||
  language ||
  '—'
const sceneText = (scene) =>
  ({ chat: '聊天分析', email: '邮件分析' })[scene] || scene || '—'

onMounted(load)
</script>

<style scoped>
.settings {
  --font-display: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, Menlo, monospace;
  display: flex;
  min-height: 100%;
  flex: 1;
  flex-direction: column;
  background: rgb(var(--c-bg));
  color: rgb(var(--c-tx));
}
.settings-head {
  display: flex;
  min-height: 56px;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 10px 28px;
}
.settings-title h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.settings-title p {
  margin: 3px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.refresh-button {
  border: 1px solid rgb(var(--c-line));
  border-radius: 7px;
  background: rgb(var(--c-panel));
  padding: 6px 11px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.refresh-button:hover {
  border-color: rgb(var(--c-tx4));
  color: rgb(var(--c-tx));
}
.refresh-button:disabled {
  opacity: 0.5;
}
.page-alert {
  flex: none;
  margin: 12px 28px 0;
  border: 1px solid rgb(var(--c-bad));
  border-radius: 8px;
  background: rgb(var(--c-bad-soft));
  padding: 9px 12px;
  color: rgb(var(--c-bad));
  font-size: 12px;
}
.settings-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.wrap {
  display: flex;
  max-width: 880px;
  margin: 0 auto;
  flex-direction: column;
  gap: 30px;
  padding: 28px 32px 56px;
}
.sect {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sh {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sh h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
}
.sh-count {
  border-radius: 999px;
  background: rgb(var(--c-chip));
  padding: 1px 7px;
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 400;
}
.sh p {
  margin: 0;
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
}
.listcard {
  display: flex;
  flex-direction: column;
  border-radius: 10px;
  background: rgb(var(--c-panel));
  box-shadow: inset 0 0 0 1px rgb(var(--c-line));
}
.device-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
}
.device-row + .device-row {
  border-top: 1px solid rgb(var(--c-line-soft));
}
.device-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}
.device-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.device-title strong {
  overflow: hidden;
  font-size: 13.5px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: rgb(var(--c-tx4));
}
.dot.online {
  background: rgb(var(--c-ok));
}
.device-state {
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.device-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.device-platform {
  color: rgb(var(--c-tx3));
  font-size: 12px;
  white-space: nowrap;
}
.revoke-button {
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 4px 8px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
  white-space: nowrap;
}
.revoke-button:hover {
  border-color: rgb(var(--c-line));
  background: rgb(var(--c-panel-sub));
  color: rgb(var(--c-bad));
}
.revoke-button:disabled {
  opacity: 0.5;
}
.kv {
  display: grid;
  grid-template-columns: 148px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  font-size: 13.5px;
}
.kv + .kv {
  border-top: 1px solid rgb(var(--c-line-soft));
}
.kv .k {
  color: rgb(var(--c-tx2));
}
.kv .v {
  min-width: 0;
}
.hint {
  color: rgb(var(--c-tx3));
  font-size: 12px;
  text-align: right;
}
.cloud-value {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}
.cloud-sub {
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.mono {
  font-family: var(--font-mono);
  font-size: 12px;
}
.state {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 26px 16px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.state strong {
  color: rgb(var(--c-tx2));
  font-size: 13px;
}
@media (max-width: 720px) {
  .settings-head {
    padding: 10px 16px;
  }
  .wrap {
    padding: 20px 16px 40px;
  }
  .page-alert {
    margin: 12px 16px 0;
  }
  .device-row {
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: flex-start;
  }
  .device-platform {
    grid-column: 1;
  }
  .revoke-button {
    grid-row: 1;
    grid-column: 2;
  }
  .kv {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .kv .hint {
    grid-column: 1 / -1;
    text-align: left;
  }
}
</style>
