<template>
  <AppLayout :padded="false">
    <div class="ws-pg">
      <header class="ws-pghead">
        <h1 class="ws-pgtitle">设备与设置</h1>
        <button
          type="button"
          class="ws-btn ghost head-refresh"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </header>

      <div v-if="error" class="ws-alert" role="alert">{{ error }}</div>

      <div class="ws-pgbody">
        <div class="ws-wrap">
          <section class="ws-sect">
            <div class="sh">
              <h2>
                已绑定设备
                <span v-if="devices.length" class="count">{{
                  devices.length
                }}</span>
              </h2>
              <p>在客户端登录这个账号即自动绑定。</p>
            </div>
            <div class="ws-listcard">
              <div v-if="loading && !devices.length" class="ws-state">
                正在加载设备…
              </div>
              <div v-else-if="!devices.length" class="ws-state">
                <strong>还没有登记设备</strong>
                <span v-if="latestUpload">
                  已检测到
                  {{ formatDate(latestUpload.created_at) }}
                  的桌面客户端上传<template v-if="latestUpload.platform"
                    >（{{ platformText(latestUpload.platform) }}）</template
                  >，但当前账号还没有可用的设备登记。
                </span>
                <span
                  >请确认客户端与当前网页使用同一服务地址和账号；重启客户端或重新打开「账户」设置后会自动登记。</span
                >
              </div>
              <template v-else>
                <div
                  v-for="device in devices"
                  :key="device.device_id"
                  class="device-row"
                >
                  <div class="device-main">
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
                    </div>
                  </div>
                  <div class="device-side">
                    <span class="mono">{{
                      platformText(device.platform)
                    }}</span>
                    <button
                      type="button"
                      class="revoke"
                      :disabled="revoking === device.device_id"
                      @click="revoke(device)"
                    >
                      {{
                        revoking === device.device_id ? '解除中…' : '解除绑定'
                      }}
                    </button>
                  </div>
                </div>
              </template>
            </div>
          </section>

          <section class="ws-sect">
            <div class="sh">
              <h2>
                采集与分析
                <span class="ro">只读</span>
              </h2>
              <p>这些默认值保存在云端，客户端上传与云端分析都按它执行。</p>
            </div>
            <div class="ws-listcard">
              <div v-if="!workflow" class="ws-state">
                {{
                  loading ? '正在加载处理默认值…' : '暂时无法读取处理默认值。'
                }}
              </div>
              <template v-else>
                <div v-for="row in analysisRows" :key="row.label" class="ws-kv">
                  <span class="k">{{ row.label }}</span>
                  <span>{{ row.value }}</span>
                  <span class="hint">{{ row.hint }}</span>
                </div>
              </template>
            </div>
          </section>

          <section class="ws-sect">
            <div class="sh">
              <h2>云端数据</h2>
              <p>
                本机原始数据库从不上传；云端只保存解析后的消息、识别结果与报告。
              </p>
            </div>
            <div class="ws-listcard">
              <div v-if="!usage" class="ws-state">
                {{ loading ? '正在加载云端用量…' : '暂时无法读取云端用量。' }}
              </div>
              <template v-else>
                <div class="ws-kv">
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
                <div class="ws-kv">
                  <span class="k">成员</span>
                  <span>{{ number(usage.member_count) }} 人</span>
                  <span class="hint">{{ memberLimitHint }}</span>
                </div>
                <div class="ws-kv">
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
const latestUpload = ref(null)
const loading = ref(false)
const revoking = ref('')
const error = ref('')

const unwrap = (response) => response.data.data || response.data

const analysisRows = computed(() => {
  const config = workflow.value
  if (!config) return []
  const preferences = config.chat_analysis_preferences
  const analysisPreferences = preferences
    ? [
        {
          label: '分析范围',
          value: (preferences.conversation_types || [])
            .map(
              (type) => ({ direct: '个人聊天', group: '群聊' })[type] || type
            )
            .join('、'),
          hint: '参与分析的聊天类型'
        },
        {
          label: '时间范围',
          value: preferences.lookback_days
            ? `最近 ${preferences.lookback_days} 天`
            : '全部记录',
          hint: '任务创建时固定'
        },
        {
          label: '事件粒度',
          value:
            { fine: '更细', balanced: '平衡', coarse: '更粗' }[
              preferences.event_granularity
            ] || '未知',
          hint: '控制事件划分的粗细'
        },
        {
          label: '摘要风格',
          value:
            {
              concise: '简洁概述',
              narrative: '背景与经过',
              actions: '行动与后续'
            }[preferences.summary_style] || '未知',
          hint: '摘要的表达方式'
        },
        {
          label: '摘要详略',
          value:
            { short: '简短', standard: '标准', detailed: '详细' }[
              preferences.summary_length
            ] || '未知',
          hint: '摘要内容的详细程度'
        }
      ]
    : []
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
    ...analysisPreferences,
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
  const [deviceResult, configResult, usageResult, uploadResult] =
    await Promise.allSettled([
      authApi.getDesktopDevices(),
      spacesApi.getWorkflowConfig(props.spaceId),
      spacesApi.getQuotaUsage(props.spaceId),
      spacesApi.getUploads(props.spaceId, { page_size: 1 })
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
  if (uploadResult.status === 'fulfilled') {
    const data = unwrap(uploadResult.value)
    const rows = Array.isArray(data) ? data : data.list || []
    latestUpload.value = rows[0] || null
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
.head-refresh {
  margin-left: auto;
}
.sh {
  display: flex;
  flex-direction: column;
  gap: 3px;
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
.sh p {
  margin: 0;
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
}
.sh .count {
  border-radius: 999px;
  background: rgb(var(--c-chip));
  padding: 1px 7px;
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 400;
}
.ro {
  border-radius: 4px;
  background: rgb(var(--c-client-soft, var(--c-ac-soft)));
  padding: 1px 6px;
  color: rgb(var(--c-client, var(--c-ac)));
  font-size: 11px;
  font-weight: 400;
}
.device-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
}
.device-row + .device-row {
  border-top: 1px solid rgb(var(--c-line-soft));
}
.device-main {
  display: flex;
  min-width: 0;
  flex: 1;
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
.device-side {
  display: flex;
  flex: none;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.device-side .mono {
  color: rgb(var(--c-tx3));
}
.revoke {
  border-radius: 6px;
  padding: 2px 0;
  color: rgb(var(--c-tx3));
  font-size: 12px;
  white-space: nowrap;
}
.revoke:hover {
  color: rgb(var(--c-bad));
}
.revoke:disabled {
  opacity: 0.5;
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
@media (max-width: 720px) {
  .device-row {
    gap: 10px;
  }
  .device-side {
    align-items: flex-end;
  }
}
</style>
