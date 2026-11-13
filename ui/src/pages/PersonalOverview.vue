<template>
  <AppLayout :padded="false">
    <div class="overview-page">
      <header class="overview-head">
        <div class="breadcrumb">
          <span>聊天记录</span><span aria-hidden="true">/</span
          ><strong>概览</strong>
        </div>
        <div class="head-actions">
          <span v-if="refreshedAt" class="updated-at"
            >更新于 {{ formatDate(refreshedAt) }}</span
          >
          <button
            type="button"
            class="refresh"
            :disabled="loading"
            @click="load"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M20 7v5h-5M4 17v-5h5" />
              <path
                d="M5.3 9a7 7 0 0 1 11.3-2L20 12M4 12l3.4 5A7 7 0 0 0 19 15"
              />
            </svg>
            刷新
          </button>
        </div>
      </header>

      <main class="overview-body">
        <div class="page-title">
          <div>
            <span class="eyebrow">CHAT WORKSPACE</span>
            <h1>概览</h1>
            <p>你的聊天记录、待处理事项与同步情况，一目了然。</p>
          </div>
          <span class="workspace-label">个人工作台</span>
        </div>

        <div v-if="error" class="error" role="alert">{{ error }}</div>
        <div v-if="loading && !showOverview" class="state" aria-busy="true">
          正在加载个人工作台…
        </div>
        <template v-if="!loading && needsTakeover">
          <section class="device-card takeover">
            <div class="device-main">
              <strong>准备个人工作台</strong>
              <p>
                当前空间还没有为这个账号准备个人工作台，准备好后即可查看概览。
              </p>
            </div>
            <button
              type="button"
              class="primary"
              :disabled="takingOver"
              @click="prepareWorkspace"
            >
              {{ takingOver ? '准备中…' : '开始准备' }}
            </button>
          </section>
        </template>
        <template v-else-if="showOverview && !needsTakeover">
          <section
            v-if="showDesktopPrompt"
            class="desktop-prompt"
            aria-label="客户端下载提示"
          >
            <img
              class="desktop-prompt-icon"
              src="/aimychats-desktop.png"
              alt="AIMyChats 客户端图标"
            />
            <div class="desktop-prompt-copy">
              <strong>连接客户端，开始同步聊天</strong>
              <p>安装 AIMyChats 客户端并登录，即可选择需要同步的聊天记录。</p>
            </div>
            <div class="desktop-prompt-actions">
              <a
                data-testid="desktop-download"
                href="https://github.com/oneprolabs/devify-desktop-releases/releases/tag/alpha"
                target="_blank"
                rel="noopener noreferrer"
                >下载 Mac 客户端</a
              ><span>适用于 Mac M 系列芯片</span>
            </div>
            <button
              type="button"
              class="desktop-prompt-close"
              aria-label="关闭下载提示"
              @click="dismissDesktopPrompt"
            >
              ×
            </button>
          </section>

          <section v-else class="device-card" aria-label="个人工作台状态">
            <span class="device-icon" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linejoin="round"
                stroke-linecap="round"
              >
                <rect x="3.5" y="4.5" width="17" height="11.5" rx="2" />
                <path d="M2 19.5h20" />
              </svg>
            </span>
            <div class="device-main">
              <strong>个人工作台</strong>
              <p>查看聊天数据与最近同步情况</p>
            </div>
            <div class="device-side">
              <span>最近一次上传</span>
              <div v-if="latestUpload" class="device-upload">
                <time>{{
                  formatDate(latestUpload.created_at) || '时间未知'
                }}</time>
                <span class="upload-status" :class="latestUpload.status">{{
                  uploadStatusText(latestUpload.status)
                }}</span>
              </div>
              <strong v-else>{{
                uploads === null ? '上传记录暂不可用' : '还没有上传记录'
              }}</strong>
            </div>
          </section>

          <section class="stats" aria-label="概览指标">
            <button
              v-for="stat in stats"
              :key="stat.target"
              type="button"
              class="stat-card"
              @click="go(stat.target)"
            >
              <span class="stat-heading">{{ stat.label }}</span>
              <strong>{{ stat.value }}</strong>
              <small>{{ stat.detail }}</small>
              <span class="stat-icon" :class="stat.target" aria-hidden="true">
                <svg
                  v-if="stat.target === 'chats'"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.7"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                >
                  <path
                    d="M20 11.5a8 8 0 0 1-8 8 8.5 8.5 0 0 1-3-.5L4 20l1.3-4a8 8 0 1 1 14.7-4.5Z"
                  />
                </svg>
                <svg
                  v-else-if="stat.target === 'events'"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.7"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                >
                  <circle cx="12" cy="12" r="8.5" />
                  <path d="m8.5 12 2.2 2.2 4.8-5" />
                </svg>
                <svg
                  v-else-if="stat.target === 'topics'"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.7"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                >
                  <path d="M5 21V4m0 0c5-3 8 3 14 0v11c-6 3-9-3-14 0" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.7"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                >
                  <path d="M6 3h8l4 4v14H6z" />
                  <path d="M14 3v5h4M9 12h6M9 16h6" />
                </svg>
              </span>
            </button>
          </section>

          <OverviewActivity
            :events="openEventsList"
            :events-available="eventsAvailable"
            :uploads="uploads || []"
            :uploads-available="uploads !== null"
            @events="go('events')"
            @sync="go('sync')"
            @open-event="openEvent"
          />
          <OverviewReport
            :report="latestReport"
            :available="reports !== null"
            @open="go('reports')"
          />

          <section class="ask-card">
            <span class="kicker" aria-hidden="true">✦</span>
            <p>
              不在电脑旁？可以直接在网页上问，例如「这周客户有哪些没回复的问题？」
            </p>
            <button type="button" @click="go('ask')">去问答 →</button>
          </section>
        </template>
      </main>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import OverviewActivity from '@/components/overview/OverviewActivity.vue'
import OverviewReport from '@/components/overview/OverviewReport.vue'
import {
  formatDate,
  uploadStatusText,
  validCount
} from '@/components/overview/formatters'
import { spacesApi } from '@/api/spaces'
import { authApi } from '@/api/auth'

const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})
const router = useRouter()
const loading = ref(false)
const needsTakeover = ref(false)
const showOverview = ref(false)
const takingOver = ref(false)
const error = ref('')
const refreshedAt = ref(null)
const openEvents = ref(null)
const inProgressEvents = ref(null)
const reports = ref(null)
const uploads = ref(null)
const conversations = ref(null)
const topics = ref(null)
let requestVersion = 0
const devicesLoaded = ref(false)
const hasDesktopDevice = ref(false)
let promptWasDismissed = false
try {
  promptWasDismissed =
    localStorage.getItem('aimychats-desktop-prompt-dismissed') === '1'
} catch {
  /* Storage may be unavailable. */
}
const dismissed = ref(promptWasDismissed)
const showDesktopPrompt = computed(
  () => devicesLoaded.value && !hasDesktopDevice.value && !dismissed.value
)
function dismissDesktopPrompt() {
  dismissed.value = true
  try {
    localStorage.setItem('aimychats-desktop-prompt-dismissed', '1')
  } catch {
    /* Keep it closed for this visit. */
  }
}
async function loadDesktopDevices(version) {
  devicesLoaded.value = false
  try {
    const data = unwrap(await authApi.getDesktopDevices())
    const list = Array.isArray(data) ? data : data?.list
    if (!Array.isArray(list)) throw new Error('Invalid device list')
    if (version !== requestVersion) return
    hasDesktopDevice.value = list.some((device) => device.status !== 'revoked')
    devicesLoaded.value = true
  } catch {
    /* Do not infer device state when the request fails. */
  }
}

// Each status is ordered by the server. Merging its first page of up to 100
// items is sufficient for the first 100 across both known unfinished statuses.
const eventsAvailable = computed(
  () => openEvents.value !== null && inProgressEvents.value !== null
)
const mergedEvents = computed(() =>
  [...(openEvents.value || []), ...(inProgressEvents.value || [])]
    .sort((a, b) => {
      const date = (item) => {
        const value = Date.parse(item.last_activity_at)
        return Number.isNaN(value) ? -Infinity : value
      }
      const aDate = date(a)
      const bDate = date(b)
      if (aDate !== bDate) return bDate > aDate ? 1 : -1
      // Date.parse truncates microseconds, but the backend orders by them.
      const micros = (item) =>
        Number(
          (
            String(item.last_activity_at || '').match(
              /\.(\d+)(?=Z|[+-]\d\d:\d\d$)/
            )?.[1] || ''
          )
            .padEnd(6, '0')
            .slice(3, 6)
        )
      const difference = micros(b) - micros(a)
      return difference || Number(b.id) - Number(a.id)
    })
    .slice(0, 100)
)
const openEventsList = computed(() => mergedEvents.value.slice(0, 5))
const enabledTopics = computed(() => {
  if (
    !topics.value ||
    !topics.value.every((item) => typeof item.enabled === 'boolean')
  )
    return null
  return topics.value.filter((item) => item.enabled).length
})
const latestReport = computed(() => reports.value?.[0] || null)
const latestUpload = computed(() => uploads.value?.[0] || null)
const messageCount = computed(() => {
  if (
    !conversations.value ||
    !conversations.value.every((item) => validCount(item.message_count))
  )
    return '—'
  const total = conversations.value.reduce(
    (sum, item) => sum + Number(item.message_count),
    0
  )
  return Number.isSafeInteger(total) ? total.toLocaleString('zh-CN') : '—'
})
const stats = computed(() => [
  {
    target: 'chats',
    label: '云端会话',
    value: conversations.value?.length ?? '—',
    detail: '当前加载的会话'
  },
  {
    target: 'events',
    label: '未完成事件',
    value: eventsAvailable.value ? mergedEvents.value.length : '—',
    detail: '最多加载前 100 个已知状态的未完成事件'
  },
  {
    target: 'topics',
    label: '主题订阅',
    value: topics.value?.length ?? '—',
    detail:
      topics.value === null
        ? '数据暂不可用'
        : enabledTopics.value === null
          ? '启用状态未知'
          : `${enabledTopics.value} 个已启用`
  },
  {
    target: 'sync',
    label: '会话消息',
    value: messageCount.value,
    detail: '已列出会话的消息数'
  }
])

const unwrap = (response) => response?.data?.data ?? response?.data
const list = (response) => {
  const data = unwrap(response)
  if (!Array.isArray(data?.list)) throw new Error('列表数据格式无效')
  return data.list
}

async function load() {
  const version = ++requestVersion
  void loadDesktopDevices(version)
  const spaceId = props.spaceId
  loading.value = true
  error.value = ''
  try {
    const spacesResponse = await spacesApi.getSpaces()
    if (version !== requestVersion) return
    const spaces = unwrap(spacesResponse)
    const spaceList = Array.isArray(spaces) ? spaces : spaces?.list
    if (!Array.isArray(spaceList)) throw new Error('空间列表数据格式无效')
    const current = spaceList.find(
      (item) => String(item.id) === String(spaceId)
    )
    if (current?.is_global_admin && !current.admin_takeover_active) {
      needsTakeover.value = true
      return
    }
    needsTakeover.value = false
    showOverview.value = true
    const sources = [
      {
        name: '未完成事件',
        target: openEvents,
        fetch: () =>
          spacesApi.getEvents(spaceId, { status: 'open', page_size: 100 }),
        parse: list
      },
      {
        name: '进行中事件',
        target: inProgressEvents,
        fetch: () =>
          spacesApi.getEvents(spaceId, {
            status: 'in_progress',
            page_size: 100
          }),
        parse: list
      },
      {
        name: '报告',
        target: reports,
        fetch: () => spacesApi.getReports(spaceId, { page_size: 20 }),
        parse: list
      },
      {
        name: '同步记录',
        target: uploads,
        fetch: () => spacesApi.getUploads(spaceId, { page_size: 20 }),
        parse: list
      },
      {
        name: '会话',
        target: conversations,
        fetch: () => spacesApi.getConversations(spaceId, { page_size: 100 }),
        parse: list
      },
      {
        name: '主题',
        target: topics,
        fetch: () => spacesApi.getTopics(spaceId),
        parse: (response) => {
          const data = unwrap(response)
          if (!Array.isArray(data)) throw new Error('主题数据格式无效')
          return data
        }
      }
    ]
    const results = await Promise.allSettled(
      sources.map(({ fetch, parse }) =>
        Promise.resolve().then(fetch).then(parse)
      )
    )
    if (version !== requestVersion) return
    const failed = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled')
        sources[index].target.value = result.value
      else failed.push({ name: sources[index].name, reason: result.reason })
    })
    if (failed.length) {
      const detail = failed
        .map(({ reason }) => reason?.response?.data?.detail)
        .find((value) => typeof value === 'string')
      error.value = `${failed.map(({ name }) => name).join('、')}加载失败${detail ? `：${detail}` : '。'} 已展示可用数据，之前的数据可能已过期。`
    } else {
      refreshedAt.value = new Date()
    }
  } catch (requestError) {
    if (version === requestVersion)
      error.value = `${requestError.response?.data?.detail || '无法加载个人工作台。'} 已有数据可能已过期。`
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

async function prepareWorkspace() {
  const spaceId = props.spaceId
  takingOver.value = true
  error.value = ''
  try {
    await spacesApi.takeoverSpace(spaceId, 'Prepare default personal workspace')
    if (String(spaceId) !== String(props.spaceId)) return
    needsTakeover.value = false
    await load()
  } catch (requestError) {
    if (String(spaceId) === String(props.spaceId)) {
      error.value =
        requestError.response?.data?.detail || '无法准备个人工作台。'
    }
  } finally {
    if (String(spaceId) === String(props.spaceId)) takingOver.value = false
  }
}

function go(target) {
  const routes = {
    chats: `/spaces/${props.spaceId}/chats`,
    events: `/spaces/${props.spaceId}/analysis`,
    topics: `/spaces/${props.spaceId}/topics`,
    reports: `/spaces/${props.spaceId}/analysis?tab=reports`,
    ask: `/spaces/${props.spaceId}/analysis?panel=ask`,
    sync: `/spaces/${props.spaceId}/operations`
  }
  router.push(routes[target])
}

function openEvent(event) {
  router.push(`/spaces/${props.spaceId}/analysis?event=${event.id}`)
}

watch(
  () => props.spaceId,
  () => {
    needsTakeover.value = false
    showOverview.value = false
    takingOver.value = false
    refreshedAt.value = null
    openEvents.value = null
    inProgressEvents.value = null
    reports.value = null
    uploads.value = null
    conversations.value = null
    topics.value = null
    load()
  },
  { immediate: true }
)
</script>

<style scoped>
.desktop-prompt {
  position: relative;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 22px 48px 22px 24px;
  margin-bottom: 22px;
  border-radius: 12px;
  background: #eef4ff;
}
.desktop-prompt-icon {
  width: 64px;
  height: 64px;
  object-fit: contain;
  border-radius: 14px;
  background: white;
  box-shadow: 0 3px 12px #344b7a1c;
}
.desktop-prompt-copy {
  flex: 1;
  min-width: 0;
}
.desktop-prompt-copy strong {
  color: #16223b;
  font-size: 17px;
}
.desktop-prompt-copy p {
  margin: 7px 0 0;
  color: #68758c;
  font-size: 13px;
  line-height: 1.6;
}
.desktop-prompt-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.desktop-prompt-actions a {
  border-radius: 8px;
  background: #465fdf;
  padding: 10px 15px;
  color: white;
  text-decoration: none;
  white-space: nowrap;
  font-size: 13px;
}
.desktop-prompt-actions span {
  color: #77849a;
  font-size: 11px;
}
.desktop-prompt-close {
  position: absolute;
  top: 10px;
  right: 14px;
  padding: 2px;
  border: 0;
  background: transparent;
  color: #8190a6;
  cursor: pointer;
  font-size: 20px;
}
@media (max-width: 760px) {
  .desktop-prompt {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
  }
  .desktop-prompt-copy {
    flex: 1 1 200px;
  }
  .desktop-prompt-actions {
    margin-left: 76px;
    align-items: flex-start;
  }
}

.overview-page {
  min-height: 100%;
  overflow: auto;
  background: rgb(var(--c-bg-sub));
  color: rgb(var(--c-tx));
}
.overview-head {
  display: flex;
  min-height: 69px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgb(var(--c-line));
  background: rgb(var(--c-panel));
  padding: 0 52px;
}
.breadcrumb {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 11px;
  color: rgb(var(--c-tx3));
  font-size: 13px;
}
.breadcrumb strong {
  color: rgb(var(--c-tx));
  font-weight: 650;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}
.updated-at {
  color: rgb(var(--c-tx3));
  font-size: 12px;
  white-space: nowrap;
}
.refresh {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 7px;
  border: 1px solid rgb(var(--c-line));
  border-radius: 8px;
  background: rgb(var(--c-panel));
  padding: 0 12px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.refresh svg {
  width: 14px;
  height: 14px;
}
.refresh:disabled {
  opacity: 0.6;
}
.overview-body {
  max-width: 1580px;
  margin: 0 auto;
  padding: 29px 42px 48px;
}
.page-title {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 21px;
}
.eyebrow {
  display: block;
  margin-bottom: 7px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.page-title h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 27px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.page-title p {
  margin: 7px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 13px;
}
.workspace-label {
  flex: none;
  border: 1px solid rgb(var(--c-line));
  border-radius: 8px;
  background: rgb(var(--c-panel));
  padding: 8px 11px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.error {
  margin-bottom: 16px;
  border: 1px solid rgb(var(--c-bad));
  border-radius: 10px;
  background: rgb(var(--c-bad-soft));
  padding: 12px 14px;
  color: rgb(var(--c-bad));
  font-size: 12px;
}
.state {
  padding: 20px 0;
  color: rgb(var(--c-tx3));
  font-size: 13px;
}
.device-card {
  display: flex;
  min-width: 0;
  min-height: 84px;
  align-items: center;
  gap: 15px;
  border: 1px solid rgb(var(--c-line));
  border-radius: 14px;
  background: linear-gradient(
    103deg,
    rgb(var(--c-ac-soft)) 0%,
    rgb(var(--c-panel)) 80%
  );
  padding: 16px 23px;
}
.device-icon {
  display: grid;
  width: 46px;
  height: 46px;
  flex: none;
  place-items: center;
  border-radius: 12px;
  background: rgb(var(--c-panel));
  color: rgb(var(--c-ac));
  box-shadow: 0 1px 5px rgb(40 52 93 / 8%);
}
.device-icon svg {
  width: 22px;
  height: 22px;
}
.device-main {
  min-width: 0;
  flex: 1;
}
.device-main strong {
  color: rgb(var(--c-tx));
  font-size: 15px;
  font-weight: 650;
}
.device-main p {
  margin: 6px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.device-side {
  min-width: 204px;
  flex: none;
  border-left: 1px solid rgb(var(--c-line));
  padding-left: 23px;
}
.device-side > span {
  display: block;
  margin-bottom: 5px;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.device-side strong,
.device-upload time {
  color: rgb(var(--c-tx2));
  font-size: 13px;
  font-weight: 650;
}
.device-upload {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.upload-status {
  border-radius: 7px;
  background: rgb(var(--c-chip));
  padding: 4px 8px;
  color: rgb(var(--c-tx2));
  font-size: 11px;
}
.upload-status.completed {
  background: rgb(var(--c-ok-soft));
  color: rgb(var(--c-ok));
}
.upload-status.failed,
.upload-status.cancelled {
  background: rgb(var(--c-bad-soft));
  color: rgb(var(--c-bad));
}
.upload-status.processing,
.upload-status.uploading {
  background: rgb(var(--c-ac-soft));
  color: rgb(var(--c-ac));
}
.takeover .primary {
  flex: none;
  border-radius: 8px;
  background: rgb(var(--c-ac));
  padding: 9px 13px;
  color: rgb(var(--c-ac-on));
  font-size: 12px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}
.stat-card {
  position: relative;
  min-width: 0;
  min-height: 111px;
  border: 1px solid rgb(var(--c-line));
  border-radius: 13px;
  background: rgb(var(--c-panel));
  padding: 16px 19px;
  text-align: left;
  box-shadow: 0 3px 14px rgb(40 52 93 / 3%);
}
.stat-card:hover {
  border-color: rgb(var(--c-ac) / 45%);
}
.stat-card span.stat-heading,
.stat-card small {
  display: block;
  padding-right: 34px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.stat-card small {
  padding-right: 0;
  font-size: 11px;
}
.stat-card strong {
  display: block;
  margin: 11px 0 7px;
  color: rgb(var(--c-tx));
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
}
.stat-icon {
  position: absolute;
  top: 17px;
  right: 18px;
  display: grid;
  width: 29px;
  height: 29px;
  place-items: center;
  border-radius: 9px;
  background: rgb(var(--c-ac-soft));
  color: rgb(var(--c-ac));
}
.stat-icon.events {
  background: rgb(var(--c-warn-soft));
  color: rgb(var(--c-warn));
}
.stat-icon.sync {
  background: rgb(var(--c-ok-soft));
  color: rgb(var(--c-ok));
}
.stat-icon svg {
  width: 15px;
  height: 15px;
}
.ask-card {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  border: 1px solid rgb(var(--c-line));
  border-radius: 12px;
  background: rgb(var(--c-panel));
  padding: 13px 20px;
}
.ask-card .kicker {
  color: rgb(var(--c-ac));
  font-size: 15px;
}
.ask-card p {
  margin: 0;
  color: rgb(var(--c-tx2));
  font-size: 12px;
  line-height: 1.6;
}
.ask-card button {
  flex: none;
  margin-left: auto;
  color: rgb(var(--c-ac));
  font-size: 12px;
}
.refresh:focus-visible,
.stat-card:focus-visible,
.ask-card button:focus-visible,
.primary:focus-visible {
  outline: 2px solid rgb(var(--c-ac));
  outline-offset: 2px;
}
@media (max-width: 1100px) {
  .overview-head {
    padding-right: 30px;
    padding-left: 30px;
  }
  .overview-body {
    padding-right: 26px;
    padding-left: 26px;
  }
}
@media (max-width: 800px) {
  .overview-head {
    min-height: 58px;
    padding-right: 18px;
    padding-left: 18px;
  }
  .overview-body {
    padding: 22px 18px 48px;
  }
  .stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .page-title h1 {
    font-size: 24px;
  }
}
@media (max-width: 540px) {
  .updated-at,
  .workspace-label {
    display: none;
  }
  .device-card {
    flex-wrap: wrap;
    padding: 16px;
  }
  .device-side {
    min-width: 0;
    flex-basis: 100%;
    border-top: 1px solid rgb(var(--c-line));
    border-left: 0;
    padding: 12px 0 0;
  }
  .stats {
    gap: 10px;
  }
  .stat-card {
    padding: 14px;
  }
  .stat-card strong {
    font-size: 24px;
  }
  .ask-card {
    flex-wrap: wrap;
  }
  .ask-card button {
    margin-left: 0;
  }
}
</style>
