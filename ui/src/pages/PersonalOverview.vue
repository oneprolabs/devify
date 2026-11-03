<template>
  <AppLayout :padded="false">
    <div class="overview-page">
      <header class="overview-head">
        <div>
          <h1>概览</h1>
          <span class="crumb">云端副本 · 截至 {{ latestAt ? formatDate(latestAt) : '暂无同步' }}</span>
        </div>
        <button type="button" class="refresh" :disabled="loading" @click="load">刷新</button>
      </header>
      <main class="overview-body">
        <div v-if="error" class="error" role="alert">{{ error }}</div>
        <div v-if="loading" class="state" aria-busy="true">正在加载个人工作台…</div>
        <template v-else-if="needsTakeover">
          <section class="device-card takeover">
            <div class="device-main">
              <div class="device-title"><strong>准备个人工作台</strong></div>
              <p>当前空间还没有为这个账号准备个人工作台，准备好后即可查看概览。</p>
            </div>
            <button type="button" class="primary" :disabled="takingOver" @click="prepareWorkspace">
              {{ takingOver ? '准备中…' : '开始准备' }}
            </button>
          </section>
        </template>
        <template v-else>
          <section class="device-card">
            <span class="device-icon" aria-hidden="true">
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round">
                <rect x="3.5" y="4.5" width="17" height="11.5" rx="2"></rect>
                <path d="M2 19.5h20"></path>
              </svg>
            </span>
            <div class="device-main">
              <div class="device-title">
                <strong>个人工作台</strong>
                <span class="device-dot" :class="{ offline: !latestAt }"></span>
                <span class="device-state">{{ latestAt ? '在线' : '待同步' }}</span>
              </div>
              <p>{{ sourceSummary }}</p>
            </div>
            <div class="device-side">
              <time>{{ latestAt ? `最近上传 ${formatDate(latestAt)}` : '还没有上传记录' }}</time>
              <small>{{ latestUpload ? `${latestUpload.message_count} 条消息 · ${statusText(latestUpload.status)}` : '上传后自动分析' }}</small>
            </div>
          </section>

          <section class="stats">
            <button type="button" @click="go('chats')">
              <span>云端会话</span>
              <strong>{{ conversations.length }}</strong>
              <small>已上传的会话</small>
            </button>
            <button type="button" @click="go('events')">
              <span>未完成事件</span>
              <strong>{{ openEvents }}</strong>
              <small>{{ openEvents ? `其中 ${openEvents} 个需要跟进` : '需要继续跟进' }}</small>
            </button>
            <button type="button" @click="go('topics')">
              <span>主题订阅</span>
              <strong>{{ topics.length }}</strong>
              <small>{{ enabledTopics }} 个运行中</small>
            </button>
            <button type="button" @click="go('sync')">
              <span>本周消息</span>
              <strong>{{ messageCount }}</strong>
              <small>已上传并分析</small>
            </button>
          </section>

          <section class="section">
            <div class="section-title">
              <h2>需要你处理<span v-if="openEventsList.length" class="count">{{ openEventsList.length }}</span></h2>
              <button type="button" @click="go('events')">全部事件 →</button>
            </div>
            <div class="list-card">
              <button
                v-for="event in openEventsList"
                :key="event.id"
                type="button"
                class="event-row"
                @click="openEvent(event)"
              >
                <span class="ring"></span>
                <strong>{{ event.title }}</strong>
                <span class="event-source">{{ eventSource(event) }}</span>
                <span class="tag">{{ statusLabel(event.status) }}</span>
              </button>
              <div v-if="!openEventsList.length" class="empty">暂无未完成事件</div>
            </div>
          </section>

          <div class="two-cols">
            <section class="section">
              <div class="section-title">
                <h2>最新报告</h2>
                <button type="button" @click="go('reports')">全部报告 →</button>
              </div>
              <button v-if="latestReport" type="button" class="report-card" @click="go('reports')">
                <div class="report-head">
                  <span class="tag">报告</span>
                  <strong>{{ latestReport.title }}</strong>
                  <small>{{ formatDate(latestReport.generated_at || latestReport.created_at) }} 生成</small>
                </div>
                <p>{{ latestReport.body || '报告正在生成或暂无正文。' }}</p>
              </button>
              <div v-else class="empty soft">还没有报告</div>
            </section>
            <section class="section">
              <div class="section-title">
                <h2>最近同步</h2>
                <button type="button" @click="go('sync')">同步记录 →</button>
              </div>
              <div class="list-card sync-list">
                <div v-for="upload in uploads.slice(0, 4)" :key="upload.id" class="sync-row">
                  <span class="sync-id">#{{ upload.id }}</span>
                  <span class="sync-time">{{ formatDate(upload.created_at) }}</span>
                  <span class="sync-count">{{ upload.message_count }} 条</span>
                  <span class="tag" :class="upload.status">{{ statusText(upload.status) }}</span>
                </div>
                <div v-if="!uploads.length" class="empty">暂无同步记录</div>
              </div>
            </section>
          </div>

          <section class="ask-card">
            <span class="kicker" aria-hidden="true">✦</span>
            <p>不在电脑旁？可以直接在网页上问，例如「这周客户有哪些没回复的问题？」</p>
            <button type="button" @click="go('ask')">去问答 →</button>
          </section>
        </template>
      </main>
    </div>
  </AppLayout>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import { spacesApi } from '@/api/spaces'

const props = defineProps({ spaceId: { type: [String, Number], required: true } })
const router = useRouter()
const loading = ref(false)
const needsTakeover = ref(false)
const takingOver = ref(false)
const error = ref('')
const events = ref([])
const reports = ref([])
const uploads = ref([])
const conversations = ref([])
const topics = ref([])

const openEvents = computed(() => events.value.filter(item => item.status !== 'done').length)
const openEventsList = computed(() => events.value.filter(item => item.status !== 'done').slice(0, 5))
const enabledTopics = computed(() => topics.value.filter(item => item.enabled).length)
const latestReport = computed(() => reports.value[0] || null)
const latestUpload = computed(() => uploads.value[0] || null)
const messageCount = computed(() =>
  conversations.value.reduce((total, item) => total + Number(item.message_count || 0), 0).toLocaleString('zh-CN')
)
const latestAt = computed(() =>
  [events.value[0]?.last_activity_at, reports.value[0]?.created_at, uploads.value[0]?.created_at]
    .filter(Boolean)
    .sort()
    .at(-1)
)
const sourceSummary = computed(() => {
  const types = [...new Set(uploads.value.map(item => item.source_type).filter(Boolean))]
  const sources = types.length ? types.join(' · ') : '微信 · 邮件'
  return `${sources} · 上传后自动解析整理`
})

const unwrap = response => (response.data.data || response.data)
const list = response => unwrap(response).list || []
const statusLabel = status => ({ open: '未完成', in_progress: '进行中', done: '已完成' })[status] || '待确认'
const statusText = status => ({ completed: '已完成', processing: '解析中', pending: '排队中', failed: '失败' })[status] || status || '待确认'
const formatDate = value => value
  ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  : ''
const eventSource = event => {
  const labels = (event.tags || []).map(tag => tag.label).filter(Boolean)
  return labels.length ? labels.slice(0, 2).join(' · ') : '云端记录'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const spacesResponse = await spacesApi.getSpaces()
    const spaces = spacesResponse.data.data || spacesResponse.data || []
    const current = (Array.isArray(spaces) ? spaces : spaces.list || []).find(
      item => String(item.id) === String(props.spaceId)
    )
    if (current?.is_global_admin && !current.admin_takeover_active) {
      needsTakeover.value = true
      return
    }
    const [eventsResponse, reportsResponse, uploadsResponse, conversationsResponse, topicsResponse] = await Promise.all([
      spacesApi.getEvents(props.spaceId, { page_size: 100 }),
      spacesApi.getReports(props.spaceId, { page_size: 20 }),
      spacesApi.getUploads(props.spaceId, { page_size: 20 }),
      spacesApi.getConversations(props.spaceId, { page_size: 100 }),
      spacesApi.getTopics(props.spaceId)
    ])
    events.value = list(eventsResponse)
    reports.value = list(reportsResponse)
    uploads.value = list(uploadsResponse)
    conversations.value = list(conversationsResponse)
    const topicData = topicsResponse.data.data || topicsResponse.data
    topics.value = Array.isArray(topicData) ? topicData : []
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '无法加载个人工作台。'
  } finally {
    loading.value = false
  }
}

async function prepareWorkspace() {
  takingOver.value = true
  try {
    await spacesApi.takeoverSpace(props.spaceId, 'Prepare default personal workspace')
    needsTakeover.value = false
    await load()
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '无法准备个人工作台。'
  } finally {
    takingOver.value = false
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

onMounted(load)
</script>
<style scoped>
.overview-page{min-height:100%;overflow:auto;background:rgb(var(--c-bg));color:rgb(var(--c-tx))}
.overview-head{display:flex;min-height:56px;align-items:center;justify-content:space-between;border-bottom:1px solid rgb(var(--c-line));padding:0 28px}
.overview-head h1{margin:0;font-family:var(--font-display);font-size:16px;font-weight:600;letter-spacing:-.01em}
.crumb{color:rgb(var(--c-tx3));font-size:13px}
.refresh,.section-title button{color:rgb(var(--c-ac));font-size:12px}
.overview-body{max-width:1000px;margin:0 auto;padding:28px 32px 56px}
.error{border:1px solid rgb(var(--c-bad));border-radius:8px;background:rgb(var(--c-bad-soft));padding:10px;color:rgb(var(--c-bad));font-size:12px}
.state,.empty{color:rgb(var(--c-tx3));font-size:12px}
.device-card{display:flex;align-items:center;gap:14px;border:1px solid rgb(var(--c-line));border-radius:10px;background:rgb(var(--c-panel));padding:16px 18px}
.device-icon{display:flex;width:38px;height:38px;flex:none;align-items:center;justify-content:center;border:1px solid rgb(var(--c-line));border-radius:9px;background:rgb(var(--c-bg-sub));color:rgb(var(--c-tx2))}
.device-main{display:flex;min-width:0;flex:1;flex-direction:column;gap:3px}
.device-title{display:flex;align-items:center;gap:8px}
.device-title strong{font-size:14px;font-weight:500}
.device-dot{width:7px;height:7px;border-radius:50%;background:rgb(var(--c-ok))}
.device-dot.offline{background:rgb(var(--c-tx4))}
.device-state{color:rgb(var(--c-tx2));font-size:12px}
.device-main p{margin:0;color:rgb(var(--c-tx3));font-size:12px}
.device-side{display:flex;flex:none;flex-direction:column;align-items:flex-end;gap:3px}
.device-side time{color:rgb(var(--c-tx2));font-family:var(--font-mono);font-size:12.5px}
.device-side small{color:rgb(var(--c-tx3));font-size:11.5px}
.takeover .primary{margin-left:auto;flex:none;border-radius:7px;background:rgb(var(--c-ac));padding:8px 13px;color:rgb(var(--c-ac-on));font-size:12px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:18px;overflow:hidden;border:1px solid rgb(var(--c-line));border-radius:10px;background:rgb(var(--c-panel))}
.stats button{padding:14px 16px;text-align:left}
.stats button+button{border-left:1px solid rgb(var(--c-line-soft))}
.stats span,.stats small{display:block;color:rgb(var(--c-tx3));font-size:12px}
.stats small{font-size:11.5px}
.stats strong{display:block;margin:6px 0 3px;font-family:var(--font-display);font-size:24px;font-weight:600;letter-spacing:-.02em}
.section{margin-top:26px}
.section-title{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.section-title h2{display:flex;align-items:center;gap:6px;margin:0;color:rgb(var(--c-tx2));font-size:12.5px;font-weight:600}
.section-title .count{border-radius:999px;background:rgb(var(--c-chip));padding:1px 6px;color:rgb(var(--c-tx3));font-family:var(--font-mono);font-size:10.5px}
.section-title button{margin-left:auto}
.list-card,.report-card{border:1px solid rgb(var(--c-line));border-radius:10px;background:rgb(var(--c-panel))}
.list-card .empty,.report-card .empty{padding:14px 16px}
.empty.soft{border:1px solid rgb(var(--c-line));border-radius:10px;background:rgb(var(--c-panel));padding:16px 18px}
.event-row{display:flex;width:100%;align-items:center;gap:10px;padding:12px 16px;text-align:left}
.event-row+.event-row,.sync-row+.sync-row{border-top:1px solid rgb(var(--c-line-soft))}
.event-row:hover,.sync-row:hover{background:rgb(var(--c-panel-sub))}
.ring{width:14px;height:14px;flex:none;border:1.5px solid rgb(var(--c-tx4));border-radius:50%}
.event-row strong{overflow:hidden;flex:1;text-overflow:ellipsis;white-space:nowrap;font-size:12.5px;font-weight:400}
.event-source{color:rgb(var(--c-tx3));font-size:12px}
.tag{flex:none;border-radius:4px;background:rgb(var(--c-warn-soft));padding:3px 7px;color:rgb(var(--c-warn));font-size:11px}
.tag.completed,.tag.done{background:rgb(var(--c-ok-soft));color:rgb(var(--c-ok))}
.tag.failed{background:rgb(var(--c-bad-soft));color:rgb(var(--c-bad))}
.two-cols{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:18px;margin-top:26px}
.two-cols .section{margin-top:0}
.report-card{display:flex;flex-direction:column;gap:10px;padding:16px 18px;text-align:left}
.report-head{display:flex;align-items:center;gap:8px}
.report-head .tag{background:rgb(var(--c-chip));color:rgb(var(--c-tx2))}
.report-head strong{min-width:0;overflow:hidden;flex:1;text-overflow:ellipsis;white-space:nowrap;font-size:14px;font-weight:500}
.report-head small{flex:none;color:rgb(var(--c-tx3));font-size:12px}
.report-card p{margin:0;color:rgb(var(--c-tx2));font-size:13px;line-height:1.8}
.sync-row{display:flex;align-items:center;gap:10px;padding:11px 16px;font-size:12.5px}
.sync-id{color:rgb(var(--c-tx2));font-family:var(--font-mono);font-size:11.5px}
.sync-time{color:rgb(var(--c-tx3));font-size:12px}
.sync-count{margin-left:auto;color:rgb(var(--c-tx2));font-size:12px}
.ask-card{display:flex;align-items:center;gap:12px;margin-top:28px;border:1px solid rgb(var(--c-line));border-radius:10px;background:rgb(var(--c-panel-sub));padding:12px 16px}
.ask-card .kicker{color:rgb(var(--c-ac));font-size:14px;line-height:1}
.ask-card p{margin:0;color:rgb(var(--c-tx2));font-size:12.5px;line-height:1.6}
.ask-card button{margin-left:auto;flex:none;color:rgb(var(--c-ac));font-size:12px}
@media(max-width:800px){.overview-body{padding:20px 18px 48px}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.stats button:nth-child(3){border-left:0;border-top:1px solid rgb(var(--c-line-soft))}.stats button:nth-child(4){border-top:1px solid rgb(var(--c-line-soft))}.two-cols{grid-template-columns:minmax(0,1fr)}.event-source{display:none}}
</style>
