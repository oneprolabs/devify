<template>
  <section class="assist" aria-label="分析辅助">
    <div class="assist-head">
      <div><div class="assist-eyebrow">ANALYSIS TOOLS</div><h2>主题与问答</h2><p>围绕当前空间的整理记录和持续事件继续追问。</p></div>
      <button type="button" class="assist-toggle" :aria-expanded="open" @click="open = !open">{{ open ? '收起' : '展开' }}</button>
    </div>
    <div v-if="open" class="assist-grid">
      <section class="topic-panel">
        <div class="panel-title"><div><h3>我的主题</h3><p>保存常用的关注范围，供后续报告使用。</p></div><button type="button" class="link-button" @click="showCreate = !showCreate">{{ showCreate ? '取消' : '新建主题' }}</button></div>
        <form v-if="showCreate" class="topic-form" @submit.prevent="createTopic">
          <label><span>主题名称</span><input v-model.trim="form.title" required maxlength="255" placeholder="例如：客户风险" /></label>
          <label><span>关注说明</span><textarea v-model.trim="form.instruction" required maxlength="5000" rows="2" placeholder="希望如何归纳这个主题？"></textarea></label>
          <button type="submit" class="primary-button" :disabled="saving">{{ saving ? '保存中…' : '保存主题' }}</button>
        </form>
        <p v-if="topicsLoading" class="assist-muted" aria-busy="true">正在加载主题…</p>
        <p v-else-if="topicError" class="assist-error" role="alert">{{ topicError }}</p>
        <p v-else-if="!topics.length" class="assist-muted">还没有保存的主题。</p>
        <div v-else class="topic-list">
          <div v-for="topic in topics" :key="topic.id" class="topic-row" :class="{ active: selectedTopic?.id === topic.id }"><button type="button" class="topic-select" @click="selectedTopic = topic"><span><strong>{{ topic.title }}</strong><small>{{ topic.instruction }}</small></span></button><button type="button" class="delete-button" :aria-label="`删除主题 ${topic.title}`" @click="deleteTopic(topic)">×</button></div>
        </div>
        <div v-if="selectedTopic" class="topic-detail"><strong>{{ selectedTopic.title }}</strong><p>{{ selectedTopic.instruction }}</p><button type="button" class="link-button" @click="askTopic">用此主题提问</button><button type="button" class="link-button" :disabled="runningTopic" @click="runTopic">{{ runningTopic ? '生成中…' : '生成主题报告' }}</button></div>
      </section>
      <section class="question-panel">
        <div class="panel-title"><div><h3>问答</h3><p>只基于当前空间已有内容回答，并显示引用。</p></div></div>
        <form class="question-form" @submit.prevent="askQuestion">
          <textarea v-model.trim="question" required maxlength="2000" rows="3" placeholder="例如：当前还有哪些未完成的客户风险？"></textarea>
          <div class="question-actions"><span>{{ selectedEvent ? `当前事件：${selectedEvent.title}` : '默认检索当前空间的近期内容' }}</span><button type="submit" class="primary-button" :disabled="asking">{{ asking ? '思考中…' : '提问' }}</button></div>
        </form>
        <p v-if="questionError" class="assist-error" role="alert">{{ questionError }}</p>
        <div v-if="questionHistory.length" class="question-history"><div class="answer-label">历史问答</div><button v-for="item in questionHistory" :key="item.id" type="button" class="history-row" @click="restoreQuestion(item)"><span>{{ item.question }}</span><small>{{ formatHistoryDate(item.created_at) }}</small></button></div>
        <article v-if="answer" class="answer" aria-live="polite"><div class="answer-label">回答</div><p>{{ answer.answer }}</p><div v-if="answer.citations?.length" class="citations"><div class="answer-label">依据</div><button v-for="citation in answer.citations" :key="`${citation.kind}-${citation.id}`" type="button" class="citation" @click="selectCitation(citation)"><span>{{ citation.kind === 'event' ? '事件' : citation.kind === 'note' ? '整理' : '消息' }} #{{ citation.id }}</span><strong>{{ citation.title }}</strong><small>{{ citation.excerpt }}</small></button></div><small class="answer-scope">已检索 {{ answer.scope?.event_ids?.length || 0 }} 件事件、{{ answer.scope?.note_ids?.length || 0 }} 条整理记录</small></article>
      </section>
    </div>
  </section>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { spacesApi } from '@/api/spaces'
const props = defineProps({ spaceId: { type: [String, Number], required: true }, selectedEvent: { type: Object, default: null } })
const emit = defineEmits(['select-citation'])
const open = ref(false)
const topics = ref([])
const selectedTopic = ref(null)
const topicsLoading = ref(false)
const topicError = ref('')
const showCreate = ref(false)
const saving = ref(false)
const asking = ref(false)
const runningTopic = ref(false)
const questionError = ref('')
const question = ref('')
const questionHistory = ref([])
const answer = ref(null)
const form = reactive({ title: '', instruction: '' })
async function loadTopics() {
  topicsLoading.value = true; topicError.value = ''
  try { const response = await spacesApi.getTopics(props.spaceId); topics.value = response.data.data || response.data || [] }  catch (error) { topicError.value = error.response?.data?.detail || '主题加载失败。' } finally { topicsLoading.value = false }
}
async function loadQuestionHistory() {
  try { const response = await spacesApi.getQuestions(props.spaceId); questionHistory.value = response.data.data || response.data || [] } catch { questionHistory.value = [] }
}
function restoreQuestion(item) { question.value = item.question; answer.value = item }
function formatHistoryDate(value) { return value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '' }
async function createTopic() {
  saving.value = true; topicError.value = ''
  try { const response = await spacesApi.createTopic(props.spaceId, { title: form.title, instruction: form.instruction, period: 'week', include_open: true, enabled: true }); const topic = response.data.data || response.data; topics.value.unshift(topic); selectedTopic.value = topic; form.title = ''; form.instruction = ''; showCreate.value = false } catch (error) { topicError.value = error.response?.data?.detail || '主题保存失败。' } finally { saving.value = false }
}
async function runTopic() { if (!selectedTopic.value) return; runningTopic.value = true; topicError.value = ''; try { await spacesApi.runTopic(selectedTopic.value.id) } catch (error) { topicError.value = error.response?.data?.detail || '主题报告生成失败。' } finally { runningTopic.value = false } }
async function deleteTopic(topic) {
  if (!window.confirm(`确定删除主题“${topic.title}”？`)) return
  try { await spacesApi.deleteTopic(topic.id); topics.value = topics.value.filter(item => item.id !== topic.id); if (selectedTopic.value?.id === topic.id) selectedTopic.value = null } catch (error) { topicError.value = error.response?.data?.detail || '主题删除失败。' }
}
function askTopic() { question.value = selectedTopic.value.instruction; askQuestion(selectedTopic.value.filters || {}) }
async function askQuestion(topicFilters = {}) {
  if (!question.value) return
  asking.value = true; questionError.value = ''; answer.value = null
  try {
    const data = { question: question.value }
    const filters = Object.fromEntries(Object.entries(topicFilters).filter(([, value]) => Array.isArray(value) && value.length))
    Object.assign(data, filters)
    if (!Object.keys(filters).length && props.selectedEvent?.id) data.event_ids = [props.selectedEvent.id]
    const response = await spacesApi.askQuestion(props.spaceId, data)
    answer.value = response.data.data || response.data
    if (answer.value.status === 'queued') {
      answer.value = await waitForAnswer(answer.value.id)
    }
    questionHistory.value = [answer.value, ...questionHistory.value.filter(item => item.id !== answer.value.id)].slice(0, 20)
  } catch (error) { questionError.value = error.response?.data?.detail || '问答暂时不可用。' } finally { asking.value = false }
}
async function waitForAnswer(questionId) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 1000))
    const response = await spacesApi.getQuestion(props.spaceId, questionId)
    const current = response.data.data || response.data
    if (current.status !== 'queued') return current
  }
  throw new Error('问答任务等待超时。')
}
function selectCitation(citation) { emit('select-citation', citation) }
onMounted(() => { loadTopics(); loadQuestionHistory() })
</script>
<style scoped>
.assist { margin: 0 40px 18px; border: 1px solid #e1e7df; border-radius: 9px; background: #fff; color: #304339; }.assist-head { display:flex; justify-content:space-between; align-items:center; padding:16px 20px; }.assist-eyebrow { color:#7b9381; font-size:10px; letter-spacing:.12em; font-weight:700; }.assist h2 { margin:5px 0 4px; font-size:16px; }.assist p { margin:0; color:#849288; font-size:11px; line-height:1.6; }.assist-toggle,.link-button { color:#538164; font-size:11px; }.assist-grid { display:grid; grid-template-columns: minmax(260px,.9fr) minmax(320px,1.1fr); border-top:1px solid #edf0eb; }.topic-panel,.question-panel { padding:18px 20px; min-width:0; }.topic-panel { border-right:1px solid #edf0eb; }.panel-title { display:flex; justify-content:space-between; gap:12px; align-items:start; }.panel-title h3 { margin:0 0 4px; font-size:13px; }.topic-form { display:grid; gap:9px; margin-top:14px; padding:12px; background:#f7f8f3; border-radius:6px; }.topic-form label { display:grid; gap:4px; color:#68786d; font-size:11px; }.topic-form input,.topic-form textarea,.question-form textarea { border:1px solid #dfe7df; border-radius:5px; background:#fff; padding:8px; color:#304339; font:inherit; font-size:12px; outline:none; }.topic-form textarea,.question-form textarea { resize:vertical; }.primary-button { justify-self:end; border-radius:5px; background:#568b68; padding:7px 12px; color:#fff; font-size:11px; }.primary-button:disabled { opacity:.55; }.assist-muted { margin-top:14px!important; }.assist-error { margin-top:12px!important; color:#a05e50!important; }.topic-list { margin-top:14px; border-top:1px solid #edf0eb; }.topic-row { display:flex; width:100%; justify-content:space-between; align-items:start; gap:8px; padding:9px 0; border-bottom:1px solid #edf0eb; text-align:left; }.topic-row.active { color:#3f7452; }.topic-select { display:flex; flex:1; min-width:0; text-align:left; }.topic-row span { display:flex; min-width:0; flex-direction:column; gap:3px; }.topic-row strong { font-size:12px; }.topic-row small { overflow:hidden; color:#87948b; font-size:11px; text-overflow:ellipsis; white-space:nowrap; }.delete-button { flex:none; color:#a4aea7; font-size:16px; }.topic-detail { margin-top:12px; border-left:2px solid #a9c9ad; padding-left:10px; }.topic-detail strong { font-size:12px; }.topic-detail p { margin:4px 0 7px; }.question-form { margin-top:14px; }.question-form textarea { width:100%; box-sizing:border-box; }.question-actions { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:8px; }.question-actions span { color:#87948b; font-size:11px; }.question-history { margin-top:14px; border-top:1px solid #edf0eb; padding-top:12px; }.history-row { display:flex; width:100%; justify-content:space-between; gap:8px; padding:7px 0; border-bottom:1px solid #f0f3ef; text-align:left; color:#53665a; font-size:11px; }.history-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.history-row small { flex:none; color:#9aa79d; font-size:10px; }.answer { margin-top:15px; border-top:1px solid #e8eee8; padding-top:14px; }.answer-label { margin-bottom:6px; color:#78947f; font-size:10px; font-weight:700; letter-spacing:.08em; }.answer > p { color:#53665a; font-size:13px; line-height:1.8; white-space:pre-wrap; }.citations { margin-top:14px; }.citation { display:grid; width:100%; gap:3px; margin-top:6px; border:1px solid #e5ece5; border-radius:5px; padding:8px; background:#fafcf9; text-align:left; }.citation span { color:#71927a; font-size:10px; }.citation strong { color:#415a4a; font-size:11px; }.citation small { overflow:hidden; color:#87948b; font-size:11px; text-overflow:ellipsis; white-space:nowrap; }.answer-scope { display:block; margin-top:12px; color:#a0aaa2; font-size:10px; }
@media(max-width:800px) { .assist { margin:0 18px 14px; }.assist-grid { display:block; }.topic-panel { border-right:0; border-bottom:1px solid #edf0eb; }.assist-head { padding:14px 16px; }.topic-panel,.question-panel { padding:15px 16px; } }
</style>
