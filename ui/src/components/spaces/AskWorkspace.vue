<template>
  <div class="flex min-h-0 flex-1">
    <aside
      class="ask-history flex w-[280px] flex-none flex-col border-r border-line bg-app-sub"
    >
      <div class="px-4 pb-3 pt-4">
        <h1
          class="font-display text-[calc(15px*var(--fs))] font-semibold text-ink"
        >
          问答
        </h1>
        <p class="mt-1 text-[calc(11.5px*var(--fs))] text-ink-3">
          基于已上传的会话与事件
        </p>
        <button
          type="button"
          class="mt-3 flex h-9 w-full items-center justify-center gap-1.5 rounded-md border border-line bg-panel text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:bg-chip hover:text-ink"
          @click="startNew"
        >
          <span aria-hidden="true">＋</span> 新对话
        </button>
      </div>
      <div
        class="font-display px-5 pb-1 pt-2 text-[calc(10.5px*var(--fs))] font-semibold tracking-[0.1em] text-ink-3"
      >
        最近
      </div>
      <div
        class="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2 pb-4"
      >
        <div
          v-if="historyLoading"
          class="px-3 py-2 text-[calc(12px*var(--fs))] text-ink-3"
          aria-busy="true"
        >
          正在加载问答记录…
        </div>
        <div
          v-else-if="!filteredThreads.length"
          class="px-3 py-2 text-[calc(12px*var(--fs))] leading-relaxed text-ink-3"
        >
          还没有保存的问答。提问后会保存在这里。
        </div>
        <button
          v-for="item in filteredThreads"
          :key="item.id"
          type="button"
          class="rounded-lg px-3 py-2.5 text-left transition-colors"
          :class="
            threadId === item.id
              ? 'bg-accent-soft text-ink'
              : 'text-ink-2 hover:bg-chip'
          "
          @click="openThread(item.id)"
        >
          <span
            class="line-clamp-2 text-[calc(13px*var(--fs))] leading-relaxed"
            >{{ item.turns[0].question }}</span
          >
          <span
            class="mt-1 block font-mono text-[calc(10.5px*var(--fs))] text-ink-3"
            >{{ historyMeta(item) }}</span
          >
        </button>
      </div>
    </aside>

    <section class="flex min-w-0 flex-1 flex-col bg-app">
      <header
        class="flex h-14 flex-none items-center gap-4 border-b border-line px-6"
      >
        <strong
          class="min-w-0 flex-1 truncate font-display text-[calc(14px*var(--fs))] font-semibold text-ink"
        >
          {{ turns[0]?.question || pendingQuestion || '问你的聊天记录' }}
        </strong>
        <div
          class="flex flex-none rounded-md border border-line bg-panel p-0.5"
        >
          <button
            v-for="option in rangeOptions"
            :key="option.value"
            type="button"
            class="rounded px-2.5 py-1 text-[calc(11.5px*var(--fs))] transition-colors"
            :class="
              range === option.value
                ? 'bg-chip font-medium text-ink'
                : 'text-ink-3 hover:text-ink'
            "
            @click="range = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </header>

      <div ref="scroller" class="min-h-0 flex-1 overflow-y-auto px-10 py-6">
        <div
          v-if="!threadId && !asking"
          class="mx-auto mt-16 max-w-[520px] text-center"
        >
          <p
            class="font-display text-[calc(16px*var(--fs))] font-semibold text-ink"
          >
            问任何关于聊天记录的问题
          </p>
          <p
            class="mt-2 text-[calc(12.5px*var(--fs))] leading-relaxed text-ink-3"
          >
            只检索已经上传到云端的会话和事件，回答会附上原文依据。
          </p>
          <div class="mt-5 flex flex-col gap-2 text-left">
            <button
              v-for="sample in samples"
              :key="sample"
              type="button"
              class="rounded-lg border border-line bg-panel px-3.5 py-2.5 text-left text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:bg-chip hover:text-ink"
              @click="ask(sample)"
            >
              {{ sample }}
            </button>
          </div>
        </div>

        <template v-else>
          <div class="mx-auto flex max-w-[820px] flex-col gap-8">
            <div v-for="turn in turns" :key="turn.id">
              <div class="flex justify-end">
                <p
                  class="max-w-[70%] rounded-[10px] bg-ink px-3.5 py-2.5 text-[calc(13px*var(--fs))] leading-relaxed text-app"
                >
                  {{ turn.question }}
                </p>
              </div>
              <div class="mt-6 flex items-start gap-3">
                <span
                  class="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-md bg-accent-soft font-display text-[calc(12px*var(--fs))] font-semibold text-accent"
                  >A</span
                >
                <div class="min-w-0 flex-1">
                  <p
                    v-if="turn.status === 'failed'"
                    class="text-[calc(13px*var(--fs))] leading-relaxed text-bad"
                  >
                    {{
                      turn.error?.startsWith('timeout:')
                        ? '这次问答超时未完成，可以重新提问。'
                        : '这次问答没有完成，可以重新提问。'
                    }}
                  </p>
                  <p
                    v-else-if="turn.status === 'queued'"
                    class="flex items-center gap-2 text-[calc(13px*var(--fs))] text-ink-3"
                    role="status"
                  >
                    <span
                      class="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent/25 border-t-accent"
                      aria-hidden="true"
                    ></span>
                    正在检索记录…
                  </p>
                  <template v-else>
                    <MarkdownRenderer
                      :content="formatAnswer(turn.answer)"
                      :enable-highlight="false"
                    />
                    <section
                      v-if="eventCitations(turn).length"
                      class="mt-6"
                    >
                      <h3
                        class="mb-2 font-display text-[calc(12.5px*var(--fs))] font-semibold text-ink"
                      >
                        相关事件
                      </h3>
                      <div
                        class="divide-y divide-line-soft overflow-hidden rounded-lg border border-line bg-panel"
                      >
                        <button
                          v-for="citation in eventCitations(turn)"
                          :key="`${turn.id}-e-${citation.id}`"
                          type="button"
                          class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-panel-sub"
                          @click="emit('select-citation', citation)"
                        >
                          <span
                            class="h-[13px] w-[13px] flex-none rounded-full border-[1.5px] border-ink-4"
                            aria-hidden="true"
                          ></span>
                          <span
                            class="min-w-0 flex-1 truncate text-[calc(13px*var(--fs))] text-ink"
                            >{{ citation.title }}</span
                          >
                          <span
                            class="flex-none text-[calc(11.5px*var(--fs))] text-ink-3"
                            >查看 →</span
                          >
                        </button>
                      </div>
                    </section>
                    <section
                      v-if="sourceCitations(turn).length"
                      class="mt-6"
                    >
                      <h3
                        class="mb-2 font-display text-[calc(12.5px*var(--fs))] font-semibold text-ink"
                      >
                        原文依据
                      </h3>
                      <div class="flex flex-col gap-2">
                        <button
                          v-for="citation in sourceCitations(turn)"
                          :key="`${turn.id}-${citation.kind}-${citation.id}`"
                          type="button"
                          class="rounded-lg border border-line bg-panel px-4 py-3 text-left transition-colors hover:bg-panel-sub"
                          @click="emit('select-citation', citation)"
                        >
                          <span
                            class="flex items-center gap-2 text-[calc(11.5px*var(--fs))] text-ink-3"
                          >
                            <span
                              class="rounded bg-chip px-1.5 py-0.5 text-[calc(10.5px*var(--fs))] text-ink-2"
                              >{{
                                citation.kind === 'note' ? '整理' : '消息'
                              }}</span
                            >
                            <span class="truncate">{{ citation.title }}</span>
                          </span>
                          <span
                            class="mt-1.5 line-clamp-3 block text-[calc(12.5px*var(--fs))] leading-relaxed text-ink-2"
                            >{{ citation.excerpt }}</span
                          >
                        </button>
                      </div>
                    </section>
                    <p
                      class="mt-5 font-mono text-[calc(10.5px*var(--fs))] text-ink-4"
                    >
                      基于 {{ scopeCounts(turn).events }} 个事件、{{
                        scopeCounts(turn).sources
                      }}
                      条原文 · 范围：{{ rangeLabel }}
                    </p>
                  </template>
                </div>
              </div>
            </div>

            <div v-if="asking">
              <div class="flex justify-end">
                <p
                  class="max-w-[70%] rounded-[10px] bg-ink px-3.5 py-2.5 text-[calc(13px*var(--fs))] leading-relaxed text-app"
                >
                  {{ pendingQuestion }}
                </p>
              </div>
              <div class="mt-6 flex items-start gap-3">
                <span
                  class="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-md bg-accent-soft font-display text-[calc(12px*var(--fs))] font-semibold text-accent"
                  >A</span
                >
                <p
                  class="flex items-center gap-2 text-[calc(13px*var(--fs))] text-ink-3"
                  role="status"
                >
                  <span
                    class="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent/25 border-t-accent"
                    aria-hidden="true"
                  ></span>
                  正在检索记录…
                </p>
              </div>
            </div>

            <p
              v-if="error"
              class="text-[calc(12px*var(--fs))] text-bad"
              role="alert"
            >
              {{ error }}
            </p>
          </div>
        </template>
      </div>

      <form
        class="flex-none border-t border-line px-10 py-4"
        @submit.prevent="ask(question)"
      >
        <div class="mx-auto max-w-[820px]">
          <div
            class="rounded-xl border border-line bg-panel px-4 py-3 focus-within:border-accent"
          >
            <textarea
              v-model="question"
              rows="2"
              maxlength="2000"
              class="w-full resize-none bg-transparent text-[calc(13.5px*var(--fs))] leading-relaxed text-ink outline-none placeholder:text-ink-4"
              placeholder="问任何关于聊天记录的问题，例如：这周客户有哪些没回复的问题？"
              @keydown.enter.exact.prevent="ask(question)"
            ></textarea>
            <div class="mt-2 flex items-center gap-2">
              <span
                class="rounded bg-panel-sub px-2 py-0.5 font-mono text-[calc(10.5px*var(--fs))] text-ink-3"
              >
                云端数据 · 截至 {{ cloudCutoff }}
              </span>
              <button
                type="submit"
                class="ml-auto flex h-7 items-center rounded-md px-3 text-[calc(12px*var(--fs))] transition-colors"
                :class="
                  canAsk ? 'bg-accent text-accent-on' : 'bg-chip text-ink-4'
                "
                :disabled="!canAsk"
              >
                {{ asking ? '思考中…' : '提问' }}
              </button>
            </div>
          </div>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { spacesApi } from '@/api/spaces'
import MarkdownRenderer from '@/components/ui/MarkdownRenderer.vue'

const props = defineProps({
  spaceId: { type: [String, Number], required: true },
  initialQuestion: { type: String, default: '' }
})
const emit = defineEmits(['select-citation'])

const history = ref([])
const threadId = ref(null)
const pendingQuestion = ref('')
const question = ref(props.initialQuestion || '')
const asking = ref(false)
const historyLoading = ref(false)
const error = ref('')
const range = ref('all')
const scroller = ref(null)

const rangeOptions = [
  { value: 'all', label: '全部' },
  { value: 'week', label: '近 7 天' },
  { value: 'today', label: '今天' }
]
const samples = [
  '这周客户有哪些没回复的问题？',
  '最近有哪些事情需要我跟进？',
  '哪些事件已经完成但还没有结论？'
]
const rangeLabel = computed(
  () =>
    rangeOptions.find((option) => option.value === range.value)?.label || '全部'
)
const canAsk = computed(
  () => Boolean(question.value.trim()) && !threadBusy.value
)
const cloudCutoff = computed(() =>
  new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
)
function threadRoot(item) {
  return item.thread_id || item.id
}
const threads = computed(() => {
  const groups = new Map()
  for (const item of history.value) {
    const key = threadRoot(item)
    const list = groups.get(key) || []
    list.push(item)
    groups.set(key, list)
  }
  return [...groups.values()]
    .map((items) => {
      const ordered = [...items].sort(
        (left, right) =>
          new Date(left.created_at).getTime() -
          new Date(right.created_at).getTime()
      )
      return {
        id: threadRoot(ordered[0]),
        turns: ordered,
        latest: ordered[ordered.length - 1]
      }
    })
    .sort(
      (left, right) =>
        new Date(right.latest.created_at).getTime() -
        new Date(left.latest.created_at).getTime()
    )
})
const filteredThreads = computed(() => {
  if (range.value === 'all') return threads.value
  const now = Date.now()
  const day = 24 * 60 * 60 * 1000
  const from = range.value === 'today' ? startOfToday() : now - 7 * day
  return threads.value.filter(
    (item) => new Date(item.latest.created_at).getTime() >= from
  )
})
const turns = computed(
  () => threads.value.find((item) => item.id === threadId.value)?.turns || []
)
const threadBusy = computed(
  () => asking.value || turns.value.some((item) => item.status === 'queued')
)
const circledNumbers = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
const numberedItem = /^\d{1,2}[.、．]\s/
const cnSection = /^[一二三四五六七八九十]、\s*(.+)$/

function formatAnswer(answer) {
  let text = String(answer || '').replace(/\r\n?/g, '\n')
  for (let index = 0; index < circledNumbers.length; index += 1) {
    text = text.replaceAll(circledNumbers[index], `\n${index + 1}. `)
  }
  text = text.replace(/[ \t]+(?=\d{1,2}[.、．]\s)/g, '\n')
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  const formatted = []
  let seenItem = false
  for (const line of lines) {
    const section = line.match(cnSection)
    if (section) {
      const [title, ...details] = section[1]
        .split(' - ')
        .map((part) => part.trim())
        .filter(Boolean)
      if (formatted.length && formatted[formatted.length - 1] !== '') {
        formatted.push('')
      }
      seenItem = true
      formatted.push(`## ${title}`)
      if (details.length) {
        formatted.push('')
        formatted.push(...details.map((part) => `- ${part}`))
      }
      continue
    }
    const item = numberedItem.test(line)
    if (item && formatted.length && !seenItem) formatted.push('')
    seenItem = seenItem || item
    formatted.push(line)
  }
  return formatted.join('\n').trim()
}

function eventCitations(turn) {
  return (turn.citations || []).filter((citation) => citation.kind === 'event')
}
function sourceCitations(turn) {
  return (turn.citations || []).filter((citation) => citation.kind !== 'event')
}
function scopeCounts(turn) {
  const sources = sourceCitations(turn)
  return {
    events: turn.scope?.event_ids?.length || eventCitations(turn).length,
    sources: sources.filter((item) => item.kind === 'message').length
  }
}

function rangeBounds() {
  const now = new Date()
  if (range.value === 'today') {
    const start = new Date(now)
    start.setHours(0, 0, 0, 0)
    const end = new Date(start)
    end.setDate(end.getDate() + 1)
    return { since: start.toISOString(), until: end.toISOString() }
  }
  if (range.value === 'week') {
    return {
      since: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      until: now.toISOString()
    }
  }
  return {}
}
function startOfToday() {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  return date.getTime()
}
function historyMeta(item) {
  if (!item.latest?.created_at) return `${item.turns.length} 轮`
  const date = new Date(item.latest.created_at)
  const stamp = date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit'
  })
  const state =
    item.latest.status === 'queued'
      ? '生成中'
      : item.latest.status === 'failed'
        ? '失败'
        : `${item.turns.length} 轮`
  return `${stamp} · ${state}`
}
function unwrap(response) {
  return response.data?.data ?? response.data
}
async function loadHistory() {
  historyLoading.value = true
  try {
    const data = unwrap(await spacesApi.getQuestions(props.spaceId))
    history.value = Array.isArray(data) ? data : data?.list || []
    if (threadId.value == null && history.value.length) {
      threadId.value = threadRoot(history.value[0])
    }
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}
function startNew() {
  threadId.value = null
  pendingQuestion.value = ''
  question.value = ''
  error.value = ''
}
function openThread(id) {
  threadId.value = id
  pendingQuestion.value = ''
  error.value = ''
}
async function ask(text) {
  const value = String(text || '').trim()
  if (!value || threadBusy.value) return
  const continuing = threadId.value
  asking.value = true
  error.value = ''
  pendingQuestion.value = value
  question.value = ''
  try {
    const payload = { question: value, ...rangeBounds() }
    if (continuing) payload.thread_id = continuing
    let answer = unwrap(await spacesApi.askQuestion(props.spaceId, payload))
    if (answer.status === 'queued') answer = await waitForAnswer(answer.id)
    answer = { ...answer, question: answer.question || value }
    threadId.value = answer.thread_id || continuing || answer.id
    history.value = [
      answer,
      ...history.value.filter((item) => item.id !== answer.id)
    ]
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  } catch (requestError) {
    error.value =
      requestError.response?.data?.detail || '问答暂时不可用，请稍后重试。'
  } finally {
    asking.value = false
  }
}
async function waitForAnswer(questionId) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    const answer = unwrap(
      await spacesApi.getQuestion(props.spaceId, questionId)
    )
    if (answer.status !== 'queued') return answer
  }
  throw new Error('问答任务等待超时。')
}
const settling = new Set()
watch(turns, (items) => {
  const queued = [...items].reverse().find((item) => item.status === 'queued')
  if (!queued || settling.has(queued.id)) return
  settling.add(queued.id)
  waitForAnswer(queued.id)
    .then((answer) => {
      history.value = history.value.map((item) =>
        item.id === answer.id ? { ...item, ...answer } : item
      )
    })
    .catch(() => {
      history.value = history.value.map((item) =>
        item.id === queued.id && item.status === 'queued'
          ? { ...item, status: 'failed', error: 'timeout:client' }
          : item
      )
    })
    .finally(() => settling.delete(queued.id))
})
onMounted(loadHistory)
watch(
  () => props.initialQuestion,
  (value) => {
    if (value) question.value = value
  }
)
watch(
  () => turns.value.length + (asking.value ? 1 : 0),
  async () => {
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  }
)
</script>

<style scoped>
@media (max-width: 768px) {
  .ask-history {
    display: none;
  }
}
</style>
