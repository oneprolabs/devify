<template>
  <AppLayout :padded="false">
    <div class="chats">
      <div v-if="error" class="page-alert" role="alert">{{ error }}</div>

      <section
        v-if="!loading && !conversations.length"
        class="onboarding"
        aria-labelledby="onboarding-title"
      >
        <div class="onboarding-copy">
          <div class="onboarding-kicker">AIMYCHATS 客户端</div>
          <h2 id="onboarding-title">
            微信和 WhatsApp 的聊天，交给电脑上的客户端整理
          </h2>
          <p>
            客户端在你的电脑上读取聊天记录并上传。上传之后，会话、事件、报告和问答都会出现在这里；服务端不读取你的本地数据库。
          </p>
        </div>
        <div class="onboarding-shot">客户端 · 聊天与事件视图</div>
        <div class="steps">
          <div v-for="step in onboardingSteps" :key="step.number" class="step">
            <span>{{ step.number }}</span>
            <div>
              <strong>{{ step.title }}</strong>
              <p>{{ step.description }}</p>
            </div>
          </div>
        </div>
        <div class="onboarding-note">
          打开已安装的客户端，登录当前账号后选择会话并确认上传。上传完成后刷新本页面即可查看。
        </div>
      </section>

      <div v-else class="split" :class="{ 'mobile-open': mobileMessage }">
        <aside class="rail" aria-labelledby="conversation-title">
          <div class="rail-head">
            <div class="rail-top">
              <div class="rail-title">
                <h1 id="conversation-title">会话</h1>
                <span>云端 {{ conversationsTotal }} · 按最后更新</span>
              </div>
              <button
                type="button"
                class="rail-refresh"
                :disabled="loading"
                aria-label="刷新会话"
                title="刷新"
                @click="loadConversations"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  aria-hidden="true"
                >
                  <path
                    d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
            </div>
            <label class="rail-search">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="6.5" />
                <path d="M16 16l4 4" stroke-linecap="round" />
              </svg>
              <input
                v-model="search"
                type="search"
                placeholder="搜索会话与聊天记录"
                aria-label="搜索会话与聊天记录"
              />
            </label>
            <div class="seg" role="group" aria-label="会话筛选">
              <button
                v-for="filter in conversationFilters"
                :key="filter.value"
                type="button"
                :class="{ on: conversationFilter === filter.value }"
                :aria-pressed="conversationFilter === filter.value"
                @click="setConversationFilter(filter.value)"
              >
                {{ filter.label }}<span>{{ filter.count }}</span>
              </button>
            </div>
          </div>

          <div class="rail-body">
            <div v-if="loading" class="rail-hint" aria-busy="true">
              正在加载会话…
            </div>
            <div
              v-else-if="!filteredConversations.length"
              class="rail-hint"
              role="status"
            >
              {{
                conversations.length
                  ? '没有符合条件的会话。'
                  : '还没有上传的会话。'
              }}
            </div>
            <template v-else>
              <button
                v-for="conversation in filteredConversations"
                :key="conversation.id"
                type="button"
                class="conv-row"
                :class="{ on: conversation.id === selectedConversation?.id }"
                @click="openConversation(conversation)"
              >
                <span class="av">
                  <img
                    v-if="conversationAvatar(conversation)"
                    :src="conversationAvatar(conversation)"
                    alt=""
                    class="av-img"
                  />
                  <template v-else>{{
                    initials(
                      conversation.title || conversation.source_conversation_id
                    )
                  }}</template>
                </span>
                <span class="conv-main">
                  <span class="conv-top">
                    <strong>{{
                      conversation.title || conversation.source_conversation_id
                    }}</strong>
                    <time
                      v-if="conversation.last_message_at"
                      :datetime="conversation.last_message_at"
                    >
                      {{ formatRowTime(conversation.last_message_at) }}
                    </time>
                  </span>
                  <span class="conv-preview">{{
                    previewLine(conversation)
                  }}</span>
                  <span class="conv-meta">
                    <span>{{ platformLabel(conversation.platform) }}</span>
                    <i>·</i>
                    <span>{{ eventCountLabel(conversation) }}</span>
                    <template v-if="conversation.pending_event_count">
                      <i>·</i>
                      <span class="pending">待处理</span>
                    </template>
                  </span>
                </span>
              </button>
              <button
                v-if="conversationsNext"
                type="button"
                class="load-more"
                :disabled="conversationsLoadingMore"
                @click="loadMoreConversations"
              >
                {{ conversationsLoadingMore ? '加载中…' : '加载更多会话' }}
              </button>
            </template>
          </div>
        </aside>

        <main class="det" aria-live="polite">
          <button
            type="button"
            class="mobile-back"
            @click="mobileMessage = false"
          >
            ← 返回会话
          </button>

          <div v-if="!selectedConversation" class="det-empty">
            <span>选择一个会话，查看它的原始记录和相关事件。</span>
          </div>

          <template v-else>
            <header class="det-head">
              <span
                class="src"
                :class="sourceClass(selectedConversation.platform)"
              >
                {{ sourceBadge(selectedConversation.platform) }}
              </span>
              <h2 class="det-name">
                {{
                  selectedConversation.title ||
                  selectedConversation.source_conversation_id
                }}
              </h2>
              <span class="det-meta">{{ selectedMeta }}</span>
              <span class="spacer" />
              <div class="seg det-tabs" role="tablist" aria-label="会话视图">
                <button
                  type="button"
                  role="tab"
                  :aria-selected="conversationView === 'events'"
                  :class="{ on: conversationView === 'events' }"
                  @click="switchConversationView('events')"
                >
                  事件<template v-if="eventTabCount !== null"
                    >&nbsp;{{ eventTabCount }}</template
                  >
                </button>
                <button
                  type="button"
                  role="tab"
                  :aria-selected="conversationView === 'raw'"
                  :class="{ on: conversationView === 'raw' }"
                  @click="switchConversationView('raw')"
                >
                  原始记录
                </button>
                <button
                  type="button"
                  role="tab"
                  :aria-selected="conversationView === 'summary'"
                  :class="{ on: conversationView === 'summary' }"
                  @click="switchConversationView('summary')"
                >
                  聊天总结
                </button>
              </div>
            </header>

            <div ref="scrollPane" class="det-body">
              <div class="det-inner">
                <p class="sync-note">
                  云端同步至
                  {{ formatDateTime(selectedConversation.last_message_at) }}
                  <template v-if="selectedConversation.last_message_at">
                    · 本机新增内容将在下次上传后出现
                  </template>
                </p>

                <section v-if="conversationView === 'events'" class="events">
                  <div v-if="eventsLoading" class="hint" aria-busy="true">
                    正在加载事件…
                  </div>
                  <div v-else-if="!conversationEvents.length" class="hint">
                    这个会话还没有关联的事件。事件会从整理后的聊天记录里出现。
                  </div>
                  <template v-else>
                    <div
                      v-for="event in conversationEvents"
                      :key="event.id"
                      class="event-block"
                    >
                      <div class="event-when">
                        <time>{{
                          formatEventWhen(
                            event.last_activity_at || event.created_at
                          )
                        }}</time>
                        <span
                          class="tag"
                          :class="event.status === 'done' ? 'ok' : 'warn'"
                        >
                          {{ statusLabel(event.status) }}
                        </span>
                      </div>
                      <article class="event-card">
                        <router-link
                          class="event-title"
                          :to="{
                            path: `/spaces/${spaceId}/analysis`,
                            query: { event: event.id }
                          }"
                        >
                          <span
                            class="ring"
                            :class="{ done: event.status === 'done' }"
                            aria-hidden="true"
                          />
                          <strong>{{ event.title }}</strong>
                        </router-link>
                        <p>{{ event.content || '暂无情况描述。' }}</p>
                        <div class="event-foot">
                          <span
                            v-for="tag in event.tags || []"
                            :key="tag.id"
                            class="tag"
                            >{{ tag.label }}</span
                          >
                          <span class="spacer" />
                          <router-link
                            :to="{
                              path: `/spaces/${spaceId}/analysis`,
                              query: { event: event.id }
                            }"
                          >
                            查看事件 →
                          </router-link>
                        </div>
                      </article>
                    </div>
                    <button
                      v-if="eventsNext"
                      type="button"
                      class="load-more"
                      :disabled="eventsLoadingMore"
                      @click="loadConversationEvents({ more: true })"
                    >
                      {{ eventsLoadingMore ? '加载中…' : '加载更多事件' }}
                    </button>
                  </template>
                </section>

                <section
                  v-else-if="conversationView === 'summary'"
                  class="summary"
                >
                  <div class="summary-empty">
                    <strong>云端还没有为这个会话生成聊天总结。</strong>
                    <p>
                      聊天总结会在云端分析任务完成之后生成，并由客户端同步到这里。当前会话只保存了原始记录，没有可展示的总结内容。
                    </p>
                  </div>
                  <p class="summary-note">
                    生成后这里会包含会话概览、参与者与关键进展。
                  </p>
                </section>

                <section v-else class="transcript">
                  <div v-if="messagesLoading" class="hint" aria-busy="true">
                    正在加载消息…
                  </div>
                  <div v-else-if="!messages.length" class="hint">
                    这个会话还没有同步到云端的消息。
                  </div>
                  <template v-else>
                    <button
                      v-if="hasEarlier"
                      type="button"
                      class="load-more earlier"
                      :disabled="messagesLoadingMore"
                      @click="loadEarlierMessages"
                    >
                      {{ messagesLoadingMore ? '加载中…' : '加载更早的消息' }}
                    </button>

                    <template
                      v-for="(message, index) in messages"
                      :key="message.id"
                    >
                      <div v-if="isNewDay(message, index)" class="daysep">
                        {{ formatDay(message.occurred_at) }}
                      </div>
                      <div
                        :id="`msg-${message.id}`"
                        class="msg"
                        :class="{ 'is-open': expandedMessageId === message.id }"
                      >
                        <span class="av msg-av">
                          <img
                            v-if="messageAvatar(message)"
                            :src="messageAvatar(message)"
                            alt=""
                            class="av-img"
                          />
                          <template v-else>{{
                            initials(message.sender_name || message.sender_key)
                          }}</template>
                        </span>
                        <div class="msg-main">
                          <div class="msg-meta">
                            <span>{{
                              message.sender_name ||
                              message.sender_key ||
                              '未知发送者'
                            }}</span>
                            <time
                              v-if="message.occurred_at"
                              :datetime="message.occurred_at"
                            >
                              {{ formatClock(message.occurred_at) }}
                            </time>
                          </div>
                          <div
                            v-if="imageParts(message).length"
                            class="bub-media"
                          >
                            <img
                              v-for="part in imageParts(message)"
                              v-show="resolveMedia(part.media_url)"
                              :key="part.id"
                              :src="resolveMedia(part.media_url)"
                              alt="图片"
                              class="bub-image"
                              loading="lazy"
                              @click="toggleMessage(message)"
                            />
                          </div>
                          <button
                            v-if="bubbleText(message)"
                            type="button"
                            class="bub"
                            :class="{ me: message.direction === 'outgoing' }"
                            :aria-expanded="expandedMessageId === message.id"
                            @click="toggleMessage(message)"
                          >
                            {{ bubbleText(message) }}
                          </button>
                          <div
                            v-if="
                              expandedMessageId === message.id &&
                              showExpandedDetail
                            "
                            class="msg-full"
                          >
                            <div
                              v-if="messageDetailLoading"
                              class="hint compact"
                            >
                              正在读取完整内容…
                            </div>
                            <template v-else-if="messageDetail?.parts?.length">
                              <div
                                v-for="part in messageDetail.parts"
                                :key="part.id"
                                class="part"
                                :class="`part-${part.kind}`"
                              >
                                <span
                                  v-if="part.kind !== 'text'"
                                  class="part-kind"
                                  >{{ partLabel(part.kind) }}</span
                                >
                                <p v-if="part.text">{{ part.text }}</p>
                                <img
                                  v-if="
                                    part.kind === 'image' &&
                                    part.media_url &&
                                    resolveMedia(part.media_url)
                                  "
                                  :src="resolveMedia(part.media_url)"
                                  :alt="partLabel(part.kind)"
                                  class="part-image"
                                  loading="lazy"
                                />
                                <video
                                  v-else-if="
                                    part.kind === 'video' && part.media_url
                                  "
                                  :src="resolveMedia(part.media_url)"
                                  controls
                                  preload="metadata"
                                  class="part-video"
                                />
                                <audio
                                  v-else-if="
                                    part.kind === 'audio' && part.media_url
                                  "
                                  :src="resolveMedia(part.media_url)"
                                  controls
                                  class="part-audio"
                                />
                                <a
                                  v-else-if="part.media_url"
                                  :href="resolveMedia(part.media_url)"
                                  target="_blank"
                                  rel="noreferrer"
                                  class="part-file"
                                >
                                  打开{{ partLabel(part.kind) }}
                                </a>
                                <small
                                  v-else-if="!part.text"
                                  class="part-state"
                                  >{{
                                    part.binding_state === 'missing'
                                      ? '原始图片未随本次上传同步'
                                      : part.binding_state
                                  }}</small
                                >
                              </div>
                            </template>
                            <p v-else class="hint compact">
                              这条消息没有可读取的正文。
                            </p>
                          </div>
                        </div>
                      </div>
                    </template>

                    <p class="transcript-foot">
                      共已加载 {{ messages.length }} 条{{
                        hasEarlier ? '，上面还有更早的消息' : ''
                      }}
                    </p>
                  </template>
                </section>
              </div>
            </div>
          </template>
        </main>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import { spacesApi } from '@/api/spaces'
import { useAvatars } from '@/composables/useAvatars'
import { useChatMedia } from '@/composables/useChatMedia'

const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})
const route = useRoute()
const { resolve: resolveAvatar } = useAvatars()
const { resolve: resolveMedia } = useChatMedia()

const MEDIA_PLACEHOLDERS = /\[(图片|视频|语音|文件)\]/g
const imageParts = (message) =>
  (message.media || []).filter(
    (part) => part.kind === 'image' && part.media_url
  )
// Show the picture instead of the "[图片]" placeholder; keep any real text.
const bubbleText = (message) => {
  const text = message.preview || ''
  if (!imageParts(message).length) return text || '（无正文）'
  return text.replace(MEDIA_PLACEHOLDERS, '').trim()
}

const conversations = ref([])
const conversationsTotal = ref(0)
const conversationsNext = ref(false)
const conversationsLoadingMore = ref(false)
const loading = ref(false)

const search = ref('')
const conversationFilter = ref('all')
const pendingConversations = ref(0)
const selectedConversation = ref(null)
const mobileMessage = ref(false)

const messages = ref([])
const messagesLoading = ref(false)
const messagesLoadingMore = ref(false)
const messagesPage = ref(1)
const hasEarlier = ref(false)
const scrollPane = ref(null)

const expandedMessageId = ref(null)
const messageDetail = ref(null)
const messageDetailLoading = ref(false)

const conversationView = ref('raw')
const conversationEvents = ref([])
const eventsLoading = ref(false)
const eventsLoadingMore = ref(false)
const eventsTotal = ref(null)
const eventsNext = ref(false)

const error = ref('')
let pendingFocusId = route.query.message_id
  ? String(route.query.message_id)
  : ''

const onboardingSteps = [
  {
    number: '1',
    title: '安装客户端',
    description: '在你的电脑上安装 Aimychats 客户端。'
  },
  {
    number: '2',
    title: '用这个账号登录',
    description: '登录后客户端会绑定当前账号，不需要在网页选择空间。'
  },
  {
    number: '3',
    title: '选择并上传范围',
    description: '选择会话、时间范围和附件策略，确认后上传。'
  },
  {
    number: '4',
    title: '回到这里查看',
    description: '上传完成后，这里会出现会话、事件、报告和问答。'
  }
]

const filteredConversations = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return conversations.value
  return conversations.value.filter((conversation) =>
    `${conversation.title || ''} ${conversation.source_conversation_id || ''} ${conversation.last_message_preview || ''}`
      .toLowerCase()
      .includes(term)
  )
})

const conversationFilters = computed(() => [
  { value: 'all', label: '全部', count: conversationsTotal.value },
  { value: 'pending', label: '有待处理', count: pendingConversations.value }
])

const eventTabCount = computed(
  () => eventsTotal.value ?? selectedConversation.value?.event_count ?? null
)

const selectedMeta = computed(() => {
  const conversation = selectedConversation.value
  if (!conversation) return ''
  const parts = [`云端 ${conversation.message_count} 条`]
  if (conversation.participant_count) {
    parts.push(`${conversation.participant_count} 人`)
  }
  parts.push(eventCountLabel(conversation))
  if (conversation.pending_event_count) parts.push('待处理')
  return parts.join(' · ')
})

const expandedParts = computed(() => messageDetail.value?.parts || [])
const showExpandedDetail = computed(() => {
  if (messageDetailLoading.value) return true
  if (!messageDetail.value) return false
  if (expandedParts.value.some((part) => part.kind !== 'text')) return true
  const fullText = expandedParts.value
    .map((part) => (part.text || '').trim())
    .filter(Boolean)
    .join(' ')
  const preview =
    messages.value.find((item) => item.id === expandedMessageId.value)
      ?.preview || ''
  return fullText !== preview
})

const initials = (value = '') => {
  const text = (value || '').trim()
  const cjk = text.match(/[\u3400-\u9fff]/)
  if (cjk) return cjk[0]
  const alnum = text.match(/[A-Za-z0-9]/)
  return alnum ? alnum[0].toUpperCase() : '?'
}
const platformLabel = (platform) =>
  ({ wechat: '微信', whatsapp: 'WhatsApp', email: '邮件', line: 'LINE' })[
    platform
  ] || '其他来源'
const sourceBadge = (platform) =>
  ({ wechat: '微', whatsapp: 'WA', email: '邮', line: 'L' })[platform] || '·'
const sourceClass = (platform) =>
  ({ wechat: 'wx', whatsapp: 'wa', email: 'mail', line: 'line' })[platform] ||
  'other'
const statusLabel = (status) =>
  ({ open: '待处理', in_progress: '进行中', done: '已完成' })[status] ||
  '进行中'
const partLabel = (kind) =>
  ({
    image: '图片',
    video: '视频',
    audio: '语音',
    file: '文件',
    quote: '引用',
    forwarded_item: '转发'
  })[kind] || kind

const previewLine = (conversation) => {
  if (!conversation.last_message_preview) return '云端还没有消息'
  const sender = conversation.last_message_sender
    ? `${conversation.last_message_sender}：`
    : ''
  return `${sender}${conversation.last_message_preview}`
}

const eventCountLabel = (conversation) =>
  conversation.event_count ? `${conversation.event_count} 个事件` : '暂无事件'

const conversationAvatar = (conversation) =>
  resolveAvatar(conversation.avatar_url)
const messageAvatar = (message) => resolveAvatar(message.sender_avatar_url)

const formatRowTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}
const formatClock = (value) =>
  value
    ? new Date(value).toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
      })
    : ''
const formatDay = (value) => {
  if (!value) return '未知日期'
  const date = new Date(value)
  return `${date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit'
  })} ${date.toLocaleDateString('zh-CN', { weekday: 'short' })}`
}
const formatDateTime = (value) =>
  value
    ? new Date(value).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    : '未知时间'
const formatEventWhen = (value) =>
  value
    ? new Date(value).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    : '时间未知'
const isNewDay = (message, index) =>
  index === 0 ||
  formatDay(message.occurred_at) !==
    formatDay(messages.value[index - 1]?.occurred_at)

const unwrap = (response) => response.data.data || response.data

const loadConversations = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = unwrap(
      await spacesApi.getConversations(props.spaceId, conversationParams())
    )
    conversations.value = data.list || []
    conversationsTotal.value =
      data.counts?.total ?? data.pagination?.total ?? conversations.value.length
    pendingConversations.value =
      data.counts?.pending ??
      conversations.value.filter((item) => item.pending_event_count).length
    conversationsNext.value = Boolean(data.pagination?.next)
    if (!conversations.value.length) {
      selectedConversation.value = null
      messages.value = []
      return
    }
    const requested = conversations.value.find(
      (item) => String(item.id) === String(route.query.conversation_id)
    )
    const current = conversations.value.find(
      (item) => item.id === selectedConversation.value?.id
    )
    const target = requested || current || conversations.value[0]
    const view = 'raw'
    if (current && target.id === current.id) {
      selectedConversation.value = target
      await loadConversationView(target)
    } else {
      if (requested) mobileMessage.value = true
      await selectConversation(target, view)
    }
  } catch (requestError) {
    error.value =
      requestError.response?.data?.detail || '会话加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

const conversationParams = () => {
  const params = { page_size: 100 }
  if (conversationFilter.value === 'pending') params.filter = 'pending'
  return params
}

const setConversationFilter = async (value) => {
  if (conversationFilter.value === value) return
  conversationFilter.value = value
  await loadConversations()
}

const loadConversationView = async (conversation) => {
  if (conversationView.value === 'raw') {
    await loadMessages(conversation)
    return
  }
  if (conversationView.value === 'summary') return
  eventsTotal.value = null
  await loadConversationEvents()
}

const openConversation = async (conversation) => {
  mobileMessage.value = true
  await selectConversation(conversation, 'raw')
}

const selectConversation = async (conversation, view = 'raw') => {
  if (!conversation) return
  selectedConversation.value = conversation
  conversationView.value = view
  conversationEvents.value = []
  eventsTotal.value = null
  eventsNext.value = false
  messages.value = []
  await loadConversationView(conversation)
}

const loadMessages = async (conversation) => {
  messagesLoading.value = true
  error.value = ''
  expandedMessageId.value = null
  messageDetail.value = null
  try {
    const focusId = pendingFocusId
    pendingFocusId = ''
    const params = { page_size: 100 }
    if (focusId) params.focus_message_id = focusId
    else params.page = 'last'
    const data = unwrap(
      await spacesApi.getMessages(props.spaceId, conversation.id, params)
    )
    messages.value = data.list || []
    messagesPage.value = data.pagination?.page || 1
    hasEarlier.value = Boolean(data.pagination?.previous)
    messagesLoading.value = false
    await nextTick()
    const target = focusId
      ? messages.value.find((item) => String(item.id) === String(focusId))
      : null
    if (target) {
      document
        .getElementById(`msg-${target.id}`)
        ?.scrollIntoView?.({ block: 'center' })
      toggleMessage(target)
    } else if (scrollPane.value) {
      scrollPane.value.scrollTop = scrollPane.value.scrollHeight
    }
  } catch (requestError) {
    error.value =
      requestError.response?.data?.detail || '消息加载失败，请稍后重试。'
  } finally {
    messagesLoading.value = false
  }
}

const loadEarlierMessages = async () => {
  if (
    !hasEarlier.value ||
    messagesLoadingMore.value ||
    !selectedConversation.value
  ) {
    return
  }
  messagesLoadingMore.value = true
  const pane = scrollPane.value
  const previousHeight = pane?.scrollHeight || 0
  try {
    const data = unwrap(
      await spacesApi.getMessages(
        props.spaceId,
        selectedConversation.value.id,
        {
          page: Math.max(1, messagesPage.value - 1),
          page_size: 100
        }
      )
    )
    messages.value = [...(data.list || []), ...messages.value]
    messagesPage.value =
      data.pagination?.page || Math.max(1, messagesPage.value - 1)
    hasEarlier.value = Boolean(data.pagination?.previous)
    await nextTick()
    if (pane) pane.scrollTop = pane.scrollHeight - previousHeight
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '更早的消息加载失败。'
  } finally {
    messagesLoadingMore.value = false
  }
}

const loadMoreConversations = async () => {
  if (!conversationsNext.value || conversationsLoadingMore.value) return
  conversationsLoadingMore.value = true
  try {
    const data = unwrap(
      await spacesApi.getConversations(props.spaceId, {
        ...conversationParams(),
        page: Math.floor(conversations.value.length / 100) + 1
      })
    )
    conversations.value = [...conversations.value, ...(data.list || [])]
    conversationsNext.value = Boolean(data.pagination?.next)
    conversationsTotal.value =
      data.pagination?.total ?? conversationsTotal.value
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '更多会话加载失败。'
  } finally {
    conversationsLoadingMore.value = false
  }
}

const loadConversationEvents = async ({ more = false } = {}) => {
  if (!selectedConversation.value) return
  if (more && (!eventsNext.value || eventsLoadingMore.value)) return
  if (more) eventsLoadingMore.value = true
  else eventsLoading.value = true
  try {
    const params = {
      conversation_id: selectedConversation.value.id,
      page_size: 100
    }
    if (more)
      params.page = Math.floor(conversationEvents.value.length / 100) + 1
    const data = unwrap(await spacesApi.getEvents(props.spaceId, params))
    conversationEvents.value = more
      ? [...conversationEvents.value, ...(data.list || [])]
      : data.list || []
    eventsTotal.value =
      data.pagination?.total ?? conversationEvents.value.length
    eventsNext.value = Boolean(data.pagination?.next)
  } catch {
    if (!more) {
      conversationEvents.value = []
      eventsTotal.value = 0
    }
    error.value = '会话事件加载失败，请稍后重试。'
  } finally {
    eventsLoading.value = false
    eventsLoadingMore.value = false
  }
}

const toggleMessage = async (message) => {
  if (expandedMessageId.value === message.id) {
    expandedMessageId.value = null
    messageDetail.value = null
    return
  }
  expandedMessageId.value = message.id
  messageDetail.value = null
  messageDetailLoading.value = true
  try {
    messageDetail.value = unwrap(
      await spacesApi.getMessage(
        props.spaceId,
        selectedConversation.value.id,
        message.id
      )
    )
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '完整消息加载失败。'
  } finally {
    messageDetailLoading.value = false
  }
}

const switchConversationView = async (view) => {
  if (conversationView.value === view) return
  conversationView.value = view
  const conversation = selectedConversation.value
  if (!conversation) return
  if (view === 'events' && eventsTotal.value === null) {
    await loadConversationEvents()
  }
  if (view === 'raw' && !messages.value.length) {
    await loadMessages(conversation)
  }
}

watch(
  () => [route.query.conversation_id, route.query.message_id],
  async ([conversationId, messageId]) => {
    if (!conversationId) return
    if (String(selectedConversation.value?.id) === String(conversationId)) {
      if (messageId) {
        pendingFocusId = String(messageId)
        conversationView.value = 'raw'
        await loadMessages(selectedConversation.value)
      }
      return
    }
    const target = conversations.value.find(
      (item) => String(item.id) === String(conversationId)
    )
    if (target) {
      pendingFocusId = messageId ? String(messageId) : ''
      mobileMessage.value = true
      await selectConversation(target, 'raw')
    }
  }
)

watch(
  () => props.spaceId,
  () => {
    selectedConversation.value = null
    messages.value = []
    mobileMessage.value = false
    loadConversations()
  }
)

onMounted(loadConversations)
</script>

<style scoped>
.chats {
  --font-display: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, Menlo, monospace;
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  background: rgb(var(--c-bg));
  color: rgb(var(--c-tx));
}
.page-alert {
  flex: none;
  margin: 10px 16px 0;
  border: 1px solid rgb(var(--c-bad));
  border-radius: 8px;
  background: rgb(var(--c-bad-soft));
  padding: 8px 12px;
  color: rgb(var(--c-bad));
  font-size: 12px;
}
.split {
  display: flex;
  flex: 1;
  min-height: 0;
}

/* left rail */
.rail {
  display: flex;
  width: 300px;
  flex: none;
  flex-direction: column;
  border-right: 1px solid rgb(var(--c-line));
  background: rgb(var(--c-panel-sub));
}
.rail-head {
  display: flex;
  flex: none;
  flex-direction: column;
  gap: 10px;
  border-bottom: 1px solid rgb(var(--c-line-soft));
  padding: 14px 14px 10px;
}
.rail-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.rail-title {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 8px;
}
.rail-title h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.rail-title span {
  color: rgb(var(--c-tx3));
  font-size: 12px;
  white-space: nowrap;
}
.rail-refresh {
  display: inline-flex;
  width: 26px;
  height: 26px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: rgb(var(--c-tx3));
}
.rail-refresh:hover {
  background: rgb(var(--c-chip));
  color: rgb(var(--c-ac));
}
.rail-refresh:disabled {
  color: rgb(var(--c-tx4));
}
.rail-search {
  display: flex;
  height: 34px;
  align-items: center;
  gap: 8px;
  border-radius: 8px;
  background: rgb(var(--c-bg));
  box-shadow: inset 0 0 0 1px rgb(var(--c-line));
  padding: 0 11px;
  color: rgb(var(--c-tx3));
}
.rail-search input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: rgb(var(--c-tx));
  font-size: 13px;
}
.rail-search input::placeholder {
  color: rgb(var(--c-tx3));
}
.seg {
  display: flex;
  gap: 2px;
  border-radius: 8px;
  background: rgb(var(--c-chip));
  padding: 2px;
}
.seg button {
  flex: 1;
  border-radius: 6px;
  padding: 5px 8px;
  color: rgb(var(--c-tx2));
  font-size: 12.5px;
  white-space: nowrap;
}
.seg button span {
  margin-left: 4px;
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  font-size: 11px;
}
.seg button.on {
  background: rgb(var(--c-panel));
  box-shadow: 0 1px 2px rgba(15, 23, 41, 0.08);
  color: rgb(var(--c-tx));
  font-weight: 500;
}
.rail-body {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  padding: 6px 8px 16px;
}
.rail-hint {
  padding: 22px 10px;
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
  line-height: 1.7;
  text-align: center;
}
.conv-row {
  display: flex;
  width: 100%;
  flex: none;
  align-items: flex-start;
  gap: 11px;
  border-radius: 8px;
  padding: 11px 10px;
  text-align: left;
}
.conv-row:hover {
  background: rgb(var(--c-chip));
}
.conv-row.on {
  background: rgb(var(--c-ac-soft));
}
.av {
  display: flex;
  width: 36px;
  height: 36px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: rgb(var(--c-chip));
  color: rgb(var(--c-tx2));
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
}
.av-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.conv-row.on .av {
  background: rgb(var(--c-panel));
  color: rgb(var(--c-ac));
}
.conv-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 3px;
}
.conv-top {
  display: flex;
  align-items: center;
  gap: 6px;
}
.conv-top strong {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 13.5px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-top time {
  flex: none;
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  font-size: 11px;
}
.conv-preview {
  overflow: hidden;
  color: rgb(var(--c-tx2));
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.conv-meta i {
  color: rgb(var(--c-tx4));
  font-style: normal;
}
.conv-meta .pending {
  color: rgb(var(--c-warn));
}

/* detail pane */
.det {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
}
.det-head {
  display: flex;
  height: 56px;
  flex: none;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgb(var(--c-line));
  background: rgb(var(--c-bg));
  padding: 0 28px;
}
.src {
  display: inline-flex;
  width: 18px;
  height: 18px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: 5px;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
}
.src.wx {
  background: #17a05d;
}
.src.wa {
  background: #128c7e;
}
.src.mail {
  background: #4a7fd9;
}
.src.line {
  background: #06c755;
}
.src.other {
  background: rgb(var(--c-tx4));
}
.det-name {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.det-meta {
  flex: none;
  color: rgb(var(--c-tx3));
  font-size: 12px;
  white-space: nowrap;
}
.det-head .spacer {
  flex: 1;
}
.det-tabs {
  width: 260px;
  flex: none;
}
.det-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.det-inner {
  display: flex;
  max-width: 820px;
  margin: 0 auto;
  flex-direction: column;
  gap: 18px;
  padding: 22px 32px 48px;
}
.sync-note {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.det-empty {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: rgb(var(--c-tx3));
  font-size: 13px;
  text-align: center;
}
.mobile-back {
  display: none;
}

/* events */
.events {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.event-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.event-when {
  display: flex;
  align-items: center;
  gap: 8px;
}
.event-when time {
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  font-size: 12px;
}
.tag {
  display: inline-flex;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgb(var(--c-chip));
  color: rgb(var(--c-tx2));
  font-size: 11.5px;
  line-height: 1.5;
  white-space: nowrap;
}
.tag.warn {
  background: rgb(var(--c-warn-soft));
  color: rgb(var(--c-warn));
}
.tag.ok {
  background: rgb(var(--c-ok-soft));
  color: rgb(var(--c-ok));
}
.event-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-radius: 10px;
  background: rgb(var(--c-panel));
  box-shadow: inset 0 0 0 1px rgb(var(--c-line));
  padding: 16px 18px;
}
.event-title {
  display: flex;
  align-items: center;
  gap: 10px;
  color: rgb(var(--c-tx));
  font-size: 15px;
  font-weight: 500;
  line-height: 1.4;
}
.event-title strong {
  min-width: 0;
  font-weight: 500;
}
.event-title:hover strong {
  color: rgb(var(--c-ac));
}
.ring {
  width: 14px;
  height: 14px;
  flex: none;
  box-sizing: border-box;
  border: 1.6px solid rgb(var(--c-tx4));
  border-radius: 50%;
}
.ring.done {
  position: relative;
  border: 0;
  background: rgb(var(--c-ok));
}
.ring.done::after {
  position: absolute;
  top: 2.5px;
  left: 4.5px;
  width: 3px;
  height: 6px;
  border: solid #fff;
  border-width: 0 1.6px 1.6px 0;
  content: '';
  transform: rotate(45deg);
}
.event-card > p {
  margin: 0;
  padding-left: 24px;
  color: rgb(var(--c-tx2));
  font-size: 13.5px;
  line-height: 1.7;
  white-space: pre-wrap;
}
.event-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  border-top: 1px solid rgb(var(--c-line-soft));
  padding: 10px 0 0 24px;
}
.event-foot .spacer {
  flex: 1;
}
.event-foot a {
  color: rgb(var(--c-ac));
  font-size: 12.5px;
  white-space: nowrap;
}

/* transcript */
.transcript {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.daysep {
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgb(var(--c-tx3));
  font-size: 11.5px;
}
.daysep::before,
.daysep::after {
  flex: 1;
  height: 1px;
  background: rgb(var(--c-line-soft));
  content: '';
}
.msg {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  scroll-margin: 80px;
}
.msg-av {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  font-size: 11.5px;
}
.msg-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}
.msg-meta {
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.msg-meta span {
  margin-right: 8px;
  color: rgb(var(--c-tx2));
  font-weight: 500;
}
.msg-meta time {
  font-family: var(--font-mono);
  font-size: 11px;
}
.bub {
  max-width: 560px;
  border-radius: 10px;
  background: rgb(var(--c-bg-sub));
  padding: 9px 12px;
  color: rgb(var(--c-tx2));
  font-size: 13.5px;
  line-height: 1.7;
  text-align: left;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.bub:hover {
  box-shadow: inset 0 0 0 1px rgb(var(--c-line));
}
.bub.me {
  background: rgb(var(--c-ac-soft));
  color: rgb(var(--c-tx));
}
.bub-media {
  display: flex;
  max-width: 560px;
  flex-wrap: wrap;
  gap: 6px;
}
.bub-image {
  display: block;
  max-width: min(320px, 100%);
  max-height: 320px;
  border-radius: 8px;
  background: rgb(var(--c-chip));
  cursor: zoom-in;
  object-fit: contain;
}
.msg.is-open .bub {
  box-shadow: inset 0 0 0 1px rgb(var(--c-ac));
}
.msg-full {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-left: 2px solid rgb(var(--c-line));
  margin-top: 2px;
  padding-left: 12px;
  color: rgb(var(--c-tx2));
  font-size: 13px;
}
.part p {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.part-image {
  display: block;
  max-width: min(420px, 100%);
  max-height: 360px;
  border-radius: 8px;
  object-fit: contain;
  background: rgb(var(--c-chip));
}
.part-video {
  display: block;
  width: min(420px, 100%);
  max-height: 360px;
  border-radius: 8px;
}
.part-audio {
  width: min(360px, 100%);
}
.part-file {
  color: rgb(var(--c-ac));
  text-decoration: none;
}
.part-file:hover {
  text-decoration: underline;
}
.part-state {
  color: rgb(var(--c-tx3));
}
.part-kind {
  color: rgb(var(--c-ac));
  font-size: 10px;
  text-transform: uppercase;
}
.transcript-foot {
  margin: 0;
  padding-top: 6px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
  text-align: center;
}

/* summary */
.summary {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.summary-empty {
  border-radius: 10px;
  background: rgb(var(--c-bg-sub));
  padding: 18px 20px;
}
.summary-empty strong {
  display: block;
  color: rgb(var(--c-tx));
  font-size: 14px;
  font-weight: 500;
}
.summary-empty p {
  margin: 8px 0 0;
  color: rgb(var(--c-tx2));
  font-size: 13.5px;
  line-height: 1.9;
}
.summary-note {
  margin: 0;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}

.hint {
  padding: 20px 0;
  color: rgb(var(--c-tx3));
  font-size: 12.5px;
  line-height: 1.7;
}
.hint.compact {
  padding: 0;
  font-size: 12px;
}
.load-more {
  width: 100%;
  border: 1px solid rgb(var(--c-line));
  border-radius: 8px;
  background: rgb(var(--c-panel));
  padding: 8px;
  color: rgb(var(--c-ac));
  font-size: 12px;
}
.load-more:disabled {
  color: rgb(var(--c-tx3));
}
.load-more.earlier {
  border-style: dashed;
  background: transparent;
}

/* onboarding */
.onboarding {
  max-width: 680px;
  margin: 0 auto;
  padding: 56px 40px 70px;
}
.onboarding-copy {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.onboarding-kicker {
  color: rgb(var(--c-ac));
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.1em;
}
.onboarding h2 {
  margin: 0;
  font-family: var(--font-display);
  color: rgb(var(--c-tx));
  font-size: 28px;
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: -0.02em;
}
.onboarding-copy > p {
  margin: 0;
  color: rgb(var(--c-tx2));
  font-size: 14.5px;
  line-height: 1.8;
}
.onboarding-shot {
  display: flex;
  height: 150px;
  align-items: center;
  justify-content: center;
  margin: 28px 0;
  border-radius: 10px;
  background: repeating-linear-gradient(
    135deg,
    rgb(var(--c-bg-sub)) 0 8px,
    rgb(var(--c-chip)) 8px 9px
  );
  box-shadow: inset 0 0 0 1px rgb(var(--c-line));
  color: rgb(var(--c-tx3));
  font-family: var(--font-mono);
  font-size: 12px;
}
.steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.step {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}
.step > span {
  display: flex;
  width: 26px;
  height: 26px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  box-shadow: inset 0 0 0 1px rgb(var(--c-line));
  color: rgb(var(--c-tx2));
  font-family: var(--font-mono);
  font-size: 12px;
}
.step strong {
  font-size: 14px;
  font-weight: 500;
}
.step p {
  margin: 4px 0 0;
  color: rgb(var(--c-tx2));
  font-size: 13px;
  line-height: 1.7;
}
.onboarding-note {
  margin-top: 24px;
  border: 1px solid rgb(var(--c-line));
  border-radius: 8px;
  background: rgb(var(--c-panel-sub));
  padding: 13px 15px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 860px) {
  .rail {
    width: 100%;
    border-right: 0;
  }
  .det {
    display: none;
  }
  .split.mobile-open .rail {
    display: none;
  }
  .split.mobile-open .det {
    display: flex;
  }
  .mobile-back {
    display: flex;
    flex: none;
    padding: 10px 16px 0;
    color: rgb(var(--c-ac));
    font-size: 12px;
  }
  .det-head {
    height: auto;
    min-height: 56px;
    flex-wrap: wrap;
    gap: 8px;
    padding: 10px 16px;
  }
  .det-name {
    flex: 1;
  }
  .det-meta {
    width: 100%;
    order: 2;
  }
  .det-head .spacer {
    display: none;
  }
  .det-tabs {
    width: 100%;
    order: 3;
  }
  .det-inner {
    padding: 18px 16px 40px;
  }
}
</style>
