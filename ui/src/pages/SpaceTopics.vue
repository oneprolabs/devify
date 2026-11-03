<template>
  <AppLayout :padded="false">
    <div class="ws-page">
      <div v-if="error" class="ws-alert" role="alert">{{ error }}</div>
      <div class="ws-split" :class="{ 'mobile-open': mobileDetail }">
        <aside class="ws-rail" aria-labelledby="topic-rail-title">
          <div class="ws-rail-head">
            <div class="ws-rail-top">
              <div class="ws-rail-title">
                <h1 id="topic-rail-title">主题订阅</h1>
                <span
                  >{{ topics.length }} 个 · {{ enabledCount }} 个运行中</span
                >
              </div>
              <button
                type="button"
                class="ws-rail-action"
                @click="toggleCreate"
              >
                {{ showCreate ? '取消' : '＋ 新建' }}
              </button>
            </div>
          </div>
          <div class="ws-rail-body">
            <div v-if="loading" class="ws-rail-hint" aria-busy="true">
              正在加载主题…
            </div>
            <div v-else-if="!topics.length" class="ws-rail-hint">
              <strong>还没有保存的主题</strong>
              新建主题后，系统会按关注范围生成报告。
            </div>
            <button
              v-for="topic in topics"
              v-else
              :key="topic.id"
              type="button"
              class="ws-row"
              :class="{ on: topic.id === selected?.id && !showCreate }"
              @click="selectTopic(topic)"
            >
              <svg
                class="ws-bell"
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M6 16.5V11a6 6 0 0112 0v5.5l1.5 1.5h-15z" />
                <path d="M10 20.5h4" />
              </svg>
              <span class="ws-row-main">
                <span class="ws-row-title">{{ topic.title }}</span>
                <span class="ws-row-sub">{{ topicMeta(topic) }}</span>
              </span>
            </button>
          </div>
          <div class="ws-rail-foot">
            <div class="ws-clhint">
              <span class="ws-clmark">a</span>
              新建主题后可以立即生成一次报告；主题由服务端按周期执行。
            </div>
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
              主题订阅 / {{ showCreate ? '新建' : selected?.title || '全部' }}
            </span>
            <div v-if="selected && !showCreate" class="ws-det-actions">
              <button
                type="button"
                class="ws-btn"
                :disabled="running"
                @click="runSelected"
              >
                {{ running ? '生成中…' : '立即生成报告' }}
              </button>
              <button
                type="button"
                class="ws-btn danger"
                @click="removeSelected"
              >
                删除
              </button>
            </div>
          </header>

          <div class="ws-det-body">
            <div v-if="showCreate" class="ws-det-inner">
              <div class="ws-det-intro">
                <h2 class="ws-display">新建主题</h2>
                <div class="ws-meta-line">
                  主题会按周期关注符合范围的事件，并在执行时生成报告。
                </div>
              </div>
              <form
                class="ws-listcard topic-form"
                @submit.prevent="createTopic"
              >
                <label class="ws-field">
                  <span>主题名称</span>
                  <input
                    v-model.trim="form.title"
                    required
                    maxlength="255"
                    placeholder="例如：客户交付风险"
                  />
                </label>
                <label class="ws-field">
                  <span>关注说明</span>
                  <textarea
                    v-model.trim="form.instruction"
                    required
                    maxlength="5000"
                    rows="4"
                    placeholder="描述希望持续关注的内容，客户端与报告会按这段说明整理。"
                  ></textarea>
                </label>
                <div class="topic-form-row">
                  <label class="ws-field">
                    <span>执行周期</span>
                    <select v-model="form.period">
                      <option value="day">每天</option>
                      <option value="week">每周</option>
                      <option value="month">每月</option>
                    </select>
                  </label>
                  <label class="ws-field">
                    <span>执行时间</span>
                    <input v-model="form.time_local" type="time" />
                  </label>
                </div>
                <div class="ws-modal-actions">
                  <button
                    type="button"
                    class="ws-btn"
                    @click="showCreate = false"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    class="ws-btn primary"
                    :disabled="saving"
                  >
                    {{ saving ? '保存中…' : '保存主题' }}
                  </button>
                </div>
              </form>
            </div>

            <div v-else-if="!selected" class="ws-state" role="status">
              <strong>选择一个主题</strong>
              <span>查看关注范围、匹配的事件和历次执行结果。</span>
            </div>

            <div v-else class="ws-det-inner">
              <div class="ws-det-intro">
                <div>
                  <span class="ws-tag" :class="selected.enabled ? 'ok' : ''">
                    {{ selected.enabled ? '运行中' : '已暂停' }}
                  </span>
                </div>
                <h2 class="ws-display">{{ selected.title }}</h2>
                <div class="ws-meta-line">{{ topicDetailMeta(selected) }}</div>
              </div>

              <div class="ws-soft">{{ selected.instruction }}</div>

              <section class="ws-sect">
                <div class="ws-sectt">
                  匹配的事件
                  <span class="n">{{ matchingEvents.length }}</span>
                  <span class="spacer"></span>
                  <span class="aside">未完成 {{ openMatchingCount }}</span>
                </div>
                <div v-if="!matchingEvents.length" class="ws-note">
                  暂无匹配事件。主题的范围由筛选条件和关键词决定。
                </div>
                <div v-else class="ws-listcard">
                  <button
                    v-for="event in matchingEvents"
                    :key="event.id"
                    type="button"
                    class="ws-li"
                    @click="openEvent(event)"
                  >
                    <span
                      class="ws-ring"
                      :class="{ done: event.status === 'done' }"
                    ></span>
                    <span class="ws-li-main">
                      <span class="ws-li-title">{{ event.title }}</span>
                    </span>
                    <span class="ws-li-meta">{{
                      statusLabel(event.status)
                    }}</span>
                  </button>
                </div>
              </section>

              <section class="ws-sect">
                <div class="ws-sectt">
                  历次执行
                  <span class="n">{{ reports.length }}</span>
                </div>
                <div v-if="!reports.length" class="ws-note">
                  还没有执行记录。点击上方「立即生成报告」可以生成一次。
                </div>
                <div v-else class="ws-listcard">
                  <button
                    v-for="report in reports"
                    :key="report.id"
                    type="button"
                    class="ws-li"
                    @click="openReport(report)"
                  >
                    <span class="ws-li-main">
                      <span class="ws-li-title">{{
                        report.title || '主题报告'
                      }}</span>
                      <span class="ws-li-sub">{{ reportMeta(report) }}</span>
                    </span>
                    <span class="ws-li-action">查看报告 →</span>
                  </button>
                </div>
              </section>

              <div class="ws-clhint">
                <span class="ws-clmark">a</span>
                主题由服务端按周期执行；立即生成会创建一份新的报告快照。
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import { spacesApi } from '@/api/spaces'

const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})
const router = useRouter()
const topics = ref([])
const events = ref([])
const reports = ref([])
const selected = ref(null)
const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const showCreate = ref(false)
const mobileDetail = ref(false)
const error = ref('')
const form = reactive({
  title: '',
  instruction: '',
  period: 'week',
  time_local: ''
})

const enabledCount = computed(
  () => topics.value.filter((topic) => topic.enabled).length
)
const matchingEvents = computed(() =>
  selected.value ? matchingFor(selected.value) : []
)
const openMatchingCount = computed(
  () => matchingEvents.value.filter((event) => event.status !== 'done').length
)

function matchingFor(topic) {
  const filters = topic.filters || {}
  if (filters.event_ids?.length)
    return events.value.filter((event) => filters.event_ids.includes(event.id))
  const keywords = (filters.keywords || []).map((value) => value.toLowerCase())
  const tagKeys = (filters.tag_keys || []).map((value) => value.toLowerCase())
  if (!keywords.length && !tagKeys.length) return events.value.slice(0, 8)
  return events.value
    .filter((event) => {
      const text = `${event.title} ${event.content || ''}`.toLowerCase()
      const tags = (event.tags || []).map((tag) =>
        `${tag.tag_key || ''} ${tag.label || ''}`.toLowerCase()
      )
      const matchesKeyword =
        !keywords.length || keywords.some((word) => text.includes(word))
      const matchesTag =
        !tagKeys.length ||
        tagKeys.some((key) => tags.some((tag) => tag.includes(key)))
      return matchesKeyword && matchesTag
    })
    .slice(0, 8)
}

const unwrap = (response) => response.data.data || response.data
const list = (response) => unwrap(response).list || []
const periodLabel = (value) =>
  ({ day: '每天', week: '每周', month: '每月' })[value] || '按计划'
const statusLabel = (value) =>
  ({ open: '未完成', in_progress: '进行中', done: '已完成' })[value] || '待确认'
const reportStatusLabel = (value) =>
  ({
    queued: '生成中',
    ready: '已生成',
    partial: '部分完成',
    failed: '失败'
  })[value] || '待生成'
const formatDate = (value) =>
  value
    ? new Date(value).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    : ''
const topicMeta = (topic) => {
  const schedule = [periodLabel(topic.period), topic.time_local?.slice(0, 5)]
    .filter(Boolean)
    .join(' ')
  const state = topic.enabled
    ? `${matchingFor(topic).filter((event) => event.status !== 'done').length} 个未完成`
    : '已暂停'
  return `${schedule} · ${state}`
}
const topicDetailMeta = (topic) => {
  const schedule = [periodLabel(topic.period), topic.time_local?.slice(0, 5)]
    .filter(Boolean)
    .join(' ')
  return [
    schedule,
    topic.timezone,
    topic.last_run_at ? `上次执行 ${formatDate(topic.last_run_at)}` : '尚未执行'
  ]
    .filter(Boolean)
    .join(' · ')
}
const reportMeta = (report) =>
  [formatDate(report.created_at), reportStatusLabel(report.status)]
    .filter(Boolean)
    .join(' · ')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [topicResponse, eventResponse] = await Promise.all([
      spacesApi.getTopics(props.spaceId),
      spacesApi.getEvents(props.spaceId, { page_size: 100 })
    ])
    const topicData = unwrap(topicResponse)
    topics.value = Array.isArray(topicData) ? topicData : []
    events.value = list(eventResponse)
    if (topics.value.length)
      await selectTopic(
        selected.value
          ? topics.value.find((item) => item.id === selected.value.id) ||
              topics.value[0]
          : topics.value[0]
      )
    else selected.value = null
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '无法加载主题订阅。'
  } finally {
    loading.value = false
  }
}
async function selectTopic(topic) {
  if (!topic) return
  selected.value = topic
  showCreate.value = false
  mobileDetail.value = true
  try {
    const data = unwrap(await spacesApi.getTopicReports(topic.id))
    reports.value = Array.isArray(data) ? data : []
  } catch {
    reports.value = []
  }
}
function toggleCreate() {
  showCreate.value = !showCreate.value
  if (showCreate.value) {
    form.title = ''
    form.instruction = ''
    form.period = 'week'
    form.time_local = ''
    mobileDetail.value = true
  }
}
async function createTopic() {
  saving.value = true
  error.value = ''
  try {
    const payload = {
      title: form.title,
      instruction: form.instruction,
      period: form.period,
      include_open: true,
      enabled: true
    }
    if (form.time_local) payload.time_local = form.time_local
    const response = await spacesApi.createTopic(props.spaceId, payload)
    showCreate.value = false
    const created = unwrap(response)
    await load()
    const topic =
      created?.id && topics.value.find((item) => item.id === created.id)
    if (topic) await selectTopic(topic)
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '主题保存失败。'
  } finally {
    saving.value = false
  }
}
async function runSelected() {
  if (!selected.value) return
  running.value = true
  error.value = ''
  try {
    const data = unwrap(await spacesApi.runTopic(selected.value.id))
    reports.value = [data, ...reports.value]
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '报告生成失败。'
  } finally {
    running.value = false
  }
}
async function removeSelected() {
  if (
    !selected.value ||
    !window.confirm(`确定删除主题“${selected.value.title}”？`)
  )
    return
  try {
    await spacesApi.deleteTopic(selected.value.id)
    selected.value = null
    reports.value = []
    await load()
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '主题删除失败。'
  }
}
function openEvent(event) {
  router.push(`/spaces/${props.spaceId}/analysis?event=${event.id}`)
}
function openReport(report) {
  router.push(
    `/spaces/${props.spaceId}/analysis?tab=reports&report=${report.id}`
  )
}
onMounted(load)
</script>

<style scoped>
.ws-det-intro {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ws-note {
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
  line-height: 1.7;
}
.ws-rail-hint strong {
  display: block;
  margin-bottom: 4px;
  color: rgb(var(--c-tx2));
  font-size: 13px;
  font-weight: 500;
}
.topic-form {
  gap: 12px;
  padding: 16px;
}
.topic-form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.topic-form select {
  width: 100%;
  border-radius: 8px;
  background: rgb(var(--c-bg));
  box-shadow: inset 0 0 0 1px rgb(var(--c-line));
  padding: 8px 10px;
  color: rgb(var(--c-tx));
  font-size: 13px;
}
</style>
