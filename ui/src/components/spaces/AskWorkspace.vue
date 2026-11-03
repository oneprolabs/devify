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
          v-else-if="!filteredHistory.length"
          class="px-3 py-2 text-[calc(12px*var(--fs))] leading-relaxed text-ink-3"
        >
          还没有保存的问答。提问后会保存在这里。
        </div>
        <button
          v-for="item in filteredHistory"
          :key="item.id"
          type="button"
          class="rounded-lg px-3 py-2.5 text-left transition-colors"
          :class="
            current?.id === item.id
              ? 'bg-accent-soft text-ink'
              : 'text-ink-2 hover:bg-chip'
          "
          @click="current = item"
        >
          <span
            class="line-clamp-2 text-[calc(13px*var(--fs))] leading-relaxed"
            >{{ item.question }}</span
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
          {{ current?.question || '问你的聊天记录' }}
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
          v-if="!current && !asking"
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
          <div class="mx-auto flex max-w-[820px] flex-col">
            <div class="flex justify-end">
              <p
                class="max-w-[70%] rounded-[10px] bg-ink px-3.5 py-2.5 text-[calc(13px*var(--fs))] leading-relaxed text-app"
              >
                {{ pendingQuestion || current?.question }}
              </p>
            </div>

            <div v-if="asking" class="mt-6 flex items-start gap-3">
              <span
                class="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-md bg-accent-soft font-display text-[calc(12px*var(--fs))] font-semibold text-accent"
                >A</span
              >
              <p class="text-[calc(13px*var(--fs))] text-ink-3">
                正在检索记录…
              </p>
            </div>

            <div v-else-if="current" class="mt-6 flex items-start gap-3">
              <span
                class="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-md bg-accent-soft font-display text-[calc(12px*var(--fs))] font-semibold text-accent"
                >A</span
              >
              <div class="min-w-0 flex-1">
                <p
                  v-if="current.status === 'failed'"
                  class="text-[calc(13px*var(--fs))] leading-relaxed text-bad"
                >
                  {{
                    current.error?.startsWith('timeout:')
                      ? '这次问答超时未完成，可以重新提问。'
                      : '这次问答没有完成，可以重新提问。'
                  }}
                </p>
                <template v-else>
                  <p
                    v-for="(paragraph, index) in answerParagraphs"
                    :key="index"
                    class="text-[calc(13.5px*var(--fs))] leading-[1.85] text-ink-2"
                    :class="{ 'mt-3': index }"
                  >
                    {{ paragraph }}
                  </p>

                  <section v-if="eventCitations.length" class="mt-6">
                    <h3
                      class="mb-2 font-display text-[calc(12.5px*var(--fs))] font-semibold text-ink"
                    >
                      相关事件
                    </h3>
                    <div
                      class="divide-y divide-line-soft overflow-hidden rounded-lg border border-line bg-panel"
                    >
                      <button
                        v-for="citation in eventCitations"
                        :key="citation.id"
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

                  <section v-if="sourceCitations.length" class="mt-6">
                    <h3
                      class="mb-2 font-display text-[calc(12.5px*var(--fs))] font-semibold text-ink"
                    >
                      原文依据
                    </h3>
                    <div class="flex flex-col gap-2">
                      <button
                        v-for="citation in sourceCitations"
                        :key="`${citation.kind}-${citation.id}`"
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
                    基于 {{ scopeCounts.events }} 个事件、{{
                      scopeCounts.sources
                    }}
                    条原文 · 范围：{{ rangeLabel }}
                  </p>
                </template>
              </div>
            </div>

            <p
              v-if="error"
              class="mt-4 text-[calc(12px*var(--fs))] text-bad"
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

const props = defineProps({
  spaceId: { type: [String, Number], required: true },
  initialQuestion: { type: String, default: '' }
})
const emit = defineEmits(['select-citation'])

const history = ref([])
const current = ref(null)
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
const canAsk = computed(() => Boolean(question.value.trim()) && !asking.value)
const cloudCutoff = computed(() =>
  new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
)
const filteredHistory = computed(() => {
  if (range.value === 'all') return history.value
  const now = Date.now()
  const day = 24 * 60 * 60 * 1000
  const from = range.value === 'today' ? startOfToday() : now - 7 * day
  return history.value.filter(
    (item) => new Date(item.created_at).getTime() >= from
  )
})
const answerParagraphs = computed(() =>
  String(current.value?.answer || '')
    .split(/\n{1,}/)
    .map((part) => part.trim())
    .filter(Boolean)
)
const citations = computed(() => current.value?.citations || [])
const eventCitations = computed(() =>
  citations.value.filter((citation) => citation.kind === 'event')
)
const sourceCitations = computed(() =>
  citations.value.filter((citation) => citation.kind !== 'event')
)
const scopeCounts = computed(() => ({
  events:
    current.value?.scope?.event_ids?.length || eventCitations.value.length,
  sources: sourceCitations.value.filter((item) => item.kind === 'message')
    .length
}))

function startOfToday() {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  return date.getTime()
}
function historyMeta(item) {
  if (!item.created_at) return ''
  const date = new Date(item.created_at)
  const stamp = date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit'
  })
  return `${stamp} · 1 轮`
}
function unwrap(response) {
  return response.data?.data ?? response.data
}
async function loadHistory() {
  historyLoading.value = true
  try {
    const data = unwrap(await spacesApi.getQuestions(props.spaceId))
    history.value = Array.isArray(data) ? data : data?.list || []
    if (!current.value && history.value.length) current.value = history.value[0]
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}
function startNew() {
  current.value = null
  pendingQuestion.value = ''
  question.value = ''
  error.value = ''
}
async function ask(text) {
  const value = String(text || '').trim()
  if (!value || asking.value) return
  asking.value = true
  error.value = ''
  pendingQuestion.value = value
  question.value = ''
  current.value = null
  try {
    let answer = unwrap(
      await spacesApi.askQuestion(props.spaceId, { question: value })
    )
    if (answer.status === 'queued') answer = await waitForAnswer(answer.id)
    current.value = { ...answer, question: answer.question || value }
    history.value = [
      current.value,
      ...history.value.filter((item) => item.id !== current.value.id)
    ]
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = 0
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
onMounted(loadHistory)
watch(
  () => props.initialQuestion,
  (value) => {
    if (value) question.value = value
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
