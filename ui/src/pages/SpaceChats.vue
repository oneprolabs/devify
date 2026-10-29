<template>
  <AppLayout :padded="false">
    <div class="workspace">
      <header class="workspace-header">
        <div class="workspace-heading">
          <router-link to="/spaces" class="workspace-back">
            {{ t('common.back') }}
          </router-link>
          <div>
            <h1>{{ space?.name || t('spaces.title') }}</h1>
            <p>{{ t('spaces.chatWorkspace') }}</p>
          </div>
        </div>
        <router-link to="/spaces" class="workspace-space-link">
          {{ t('spaces.switchSpace') }}
        </router-link>
      </header>

      <div v-if="error" class="workspace-alert" role="alert">{{ error }}</div>

      <div class="workspace-body">
        <aside class="conversation-rail" aria-labelledby="conversation-title">
          <div class="rail-head">
            <div>
              <h2 id="conversation-title">{{ t('spaces.conversations') }}</h2>
              <span>{{ conversations.length }}</span>
            </div>
            <button
              type="button"
              class="rail-refresh"
              :disabled="loading"
              @click="loadConversations"
            >
              {{ t('common.refresh') }}
            </button>
          </div>
          <label class="rail-search">
            <span class="sr-only">{{ t('common.search') }}</span>
            <input
              v-model="search"
              type="search"
              :placeholder="t('spaces.searchConversations')"
            />
          </label>

          <div v-if="loading" class="workspace-loading" aria-busy="true">
            {{ t('common.loading') }}
          </div>
          <div
            v-else-if="!filteredConversations.length"
            class="workspace-empty"
            role="status"
          >
            <strong>{{ t('spaces.noConversations') }}</strong>
            <span>{{ t('spaces.noConversationsBody') }}</span>
          </div>
          <div v-else class="conversation-list" role="list">
            <button
              v-for="conversation in filteredConversations"
              :key="conversation.id"
              type="button"
              class="conversation-row"
              :class="{ active: conversation.id === selectedConversation?.id }"
              role="listitem"
              @click="selectConversation(conversation)"
            >
              <span class="conversation-avatar">{{
                initials(conversation.title)
              }}</span>
              <span class="conversation-copy">
                <strong>{{
                  conversation.title || conversation.source_conversation_id
                }}</strong>
                <small
                  >{{ conversation.platform }} ·
                  {{ conversation.message_count }}
                  {{ t('spaces.messages') }}</small
                >
              </span>
              <time
                v-if="conversation.last_message_at"
                :datetime="conversation.last_message_at"
              >
                {{ formatDate(conversation.last_message_at) }}
              </time>
            </button>
          </div>
        </aside>

        <main class="message-panel" aria-live="polite">
          <div
            v-if="!selectedConversation"
            class="workspace-empty panel-empty"
            role="status"
          >
            <strong>{{ t('spaces.selectConversation') }}</strong>
            <span>{{ t('spaces.selectConversationBody') }}</span>
          </div>
          <template v-else>
            <div class="message-head">
              <div>
                <h2>
                  {{
                    selectedConversation.title ||
                    selectedConversation.source_conversation_id
                  }}
                </h2>
                <p>
                  {{ selectedConversation.platform }} ·
                  {{ selectedConversation.source_namespace }}
                </p>
              </div>
              <span class="message-count"
                >{{ messages.length }} {{ t('spaces.messages') }}</span
              >
            </div>
            <div
              v-if="messagesLoading"
              class="workspace-loading"
              aria-busy="true"
            >
              {{ t('common.loading') }}
            </div>
            <div
              v-else-if="!messages.length"
              class="workspace-empty panel-empty"
              role="status"
            >
              <strong>{{ t('spaces.noMessages') }}</strong>
              <span>{{ t('spaces.noMessagesBody') }}</span>
            </div>
            <div v-else class="message-layout">
              <div class="message-list" role="list">
                <button
                  v-for="message in messages"
                  :key="message.id"
                  type="button"
                  class="message-row"
                  :class="{ active: message.id === selectedMessage?.id }"
                  role="listitem"
                  @click="selectMessage(message)"
                >
                  <span class="message-meta">
                    <strong>{{
                      message.sender_name ||
                      message.sender_key ||
                      t('spaces.unknownSender')
                    }}</strong>
                    <time
                      v-if="message.occurred_at"
                      :datetime="message.occurred_at"
                      >{{ formatDateTime(message.occurred_at) }}</time
                    >
                  </span>
                  <span class="message-row-sub"
                    >#{{ message.ingest_seq }} ·
                    {{ message.normalization_state }}</span
                  >
                </button>
              </div>
              <article v-if="selectedMessage" class="message-detail">
                <div class="detail-meta">
                  <strong>{{
                    selectedMessage.sender_name ||
                    selectedMessage.sender_key ||
                    t('spaces.unknownSender')
                  }}</strong>
                  <span>{{ selectedMessage.message_key }}</span>
                </div>
                <div v-if="messageDetailLoading" class="workspace-loading">
                  {{ t('common.loading') }}
                </div>
                <div v-else-if="messageDetail?.parts?.length" class="parts">
                  <div
                    v-for="part in messageDetail.parts"
                    :key="part.id"
                    class="part"
                    :class="`part-${part.kind}`"
                  >
                    <span v-if="part.kind !== 'text'" class="part-kind">{{
                      part.kind
                    }}</span>
                    <p v-if="part.text">{{ part.text }}</p>
                    <small v-else>{{ part.binding_state }}</small>
                  </div>
                </div>
                <p v-else class="detail-empty">
                  {{ t('spaces.noMessageContent') }}
                </p>
              </article>
            </div>
          </template>
        </main>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { spacesApi } from '@/api/spaces'

const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})
const { t } = useI18n()
const space = ref(null)
const conversations = ref([])
const messages = ref([])
const selectedConversation = ref(null)
const selectedMessage = ref(null)
const messageDetail = ref(null)
const search = ref('')
const loading = ref(false)
const messagesLoading = ref(false)
const messageDetailLoading = ref(false)
const error = ref('')

const filteredConversations = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return conversations.value
  return conversations.value.filter((conversation) =>
    `${conversation.title} ${conversation.source_conversation_id} ${conversation.platform}`
      .toLowerCase()
      .includes(term)
  )
})

const initials = (value = '') => value.trim().slice(0, 1).toUpperCase() || '?'
const formatDate = (value) =>
  new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(
    new Date(value)
  )
const formatDateTime = (value) =>
  new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))

const loadConversations = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await spacesApi.getConversations(props.spaceId, {
      page_size: 100
    })
    const data = response.data.data || response.data
    conversations.value = data.list || []
    if (conversations.value.length && !selectedConversation.value)
      selectConversation(conversations.value[0])
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    loading.value = false
  }
}

const selectConversation = async (conversation) => {
  selectedConversation.value = conversation
  selectedMessage.value = null
  messageDetail.value = null
  messagesLoading.value = true
  try {
    const response = await spacesApi.getMessages(
      props.spaceId,
      conversation.id,
      { page_size: 100 }
    )
    const data = response.data.data || response.data
    messages.value = data.list || []
    if (messages.value.length) selectMessage(messages.value[0])
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    messagesLoading.value = false
  }
}

const selectMessage = async (message) => {
  selectedMessage.value = message
  messageDetailLoading.value = true
  try {
    const response = await spacesApi.getMessage(
      props.spaceId,
      selectedConversation.value.id,
      message.id
    )
    messageDetail.value = response.data.data || response.data
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    messageDetailLoading.value = false
  }
}

watch(
  () => props.spaceId,
  () => {
    selectedConversation.value = null
    loadConversations()
  }
)
onMounted(loadConversations)
</script>

<style scoped>
.workspace {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  background: rgb(var(--c-bg));
  color: rgb(var(--c-tx));
}
.workspace-header {
  display: flex;
  min-height: 57px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 10px 20px;
}
.workspace-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.workspace-back,
.workspace-space-link {
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.workspace-back:hover,
.workspace-space-link:hover {
  color: rgb(var(--c-ac));
}
.workspace-heading h1,
.message-head h2 {
  margin: 0;
  font-size: 15px;
}
.workspace-heading p,
.message-head p {
  margin: 3px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.workspace-alert {
  margin: 12px 20px 0;
  border: 1px solid rgb(var(--c-bad));
  border-radius: 6px;
  background: rgb(var(--c-bad-soft));
  padding: 9px 12px;
  color: rgb(var(--c-bad));
  font-size: 12px;
}
.workspace-body {
  display: flex;
  min-height: 0;
  flex: 1;
}
.conversation-rail {
  display: flex;
  width: 340px;
  flex-shrink: 0;
  flex-direction: column;
  border-right: 1px solid rgb(var(--c-line));
}
.rail-head,
.message-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 14px 16px;
}
.rail-head div {
  display: flex;
  align-items: baseline;
  gap: 7px;
}
.rail-head h2 {
  margin: 0;
  font-size: 13px;
}
.rail-head span,
.message-count {
  color: rgb(var(--c-tx3));
  font-family: ui-monospace, monospace;
  font-size: 10px;
}
.rail-refresh {
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.rail-refresh:hover {
  color: rgb(var(--c-ac));
}
.rail-search {
  padding: 10px 12px;
}
.rail-search input {
  width: 100%;
  border: 1px solid rgb(var(--c-line));
  border-radius: 6px;
  background: rgb(var(--c-panel-sub));
  padding: 7px 9px;
  color: rgb(var(--c-tx));
  font-size: 12px;
  outline: none;
}
.rail-search input:focus {
  border-color: rgb(var(--c-ac));
}
.conversation-list,
.message-list {
  min-height: 0;
  overflow-y: auto;
  padding: 4px 8px;
}
.conversation-list {
  flex: 1;
}
.conversation-row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 9px;
  border-radius: 7px;
  padding: 10px 8px;
  text-align: left;
}
.conversation-row:hover,
.conversation-row.active,
.message-row:hover,
.message-row.active {
  background: rgb(var(--c-ac-soft));
}
.conversation-avatar {
  display: grid;
  width: 28px;
  height: 28px;
  flex: none;
  place-items: center;
  border-radius: 6px;
  background: rgb(var(--c-chip));
  color: rgb(var(--c-ac));
  font-family: ui-monospace, monospace;
  font-size: 11px;
}
.conversation-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 3px;
}
.conversation-copy strong {
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conversation-copy small,
.conversation-row time {
  color: rgb(var(--c-tx3));
  font-size: 10px;
}
.conversation-row time {
  flex: none;
  align-self: flex-start;
}
.message-panel {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}
.message-layout {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(190px, 0.8fr) minmax(280px, 1.3fr);
}
.message-list {
  border-right: 1px solid rgb(var(--c-line));
}
.message-row {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 5px;
  border-radius: 6px;
  padding: 9px 10px;
  text-align: left;
}
.message-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.message-meta strong {
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.message-meta time,
.message-row-sub {
  color: rgb(var(--c-tx3));
  font-size: 10px;
}
.message-detail {
  min-width: 0;
  overflow-y: auto;
  padding: 22px;
}
.detail-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding-bottom: 13px;
}
.detail-meta strong {
  color: rgb(var(--c-tx));
  font-size: 14px;
}
.detail-meta span {
  color: rgb(var(--c-tx3));
  font-family: ui-monospace, monospace;
  font-size: 10px;
  word-break: break-all;
}
.parts {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 18px;
}
.part {
  border-left: 2px solid rgb(var(--c-ac));
  padding-left: 12px;
}
.part p {
  margin: 0;
  white-space: pre-wrap;
  color: rgb(var(--c-tx));
  font-size: 14px;
  line-height: 1.7;
}
.part-kind {
  display: block;
  margin-bottom: 4px;
  color: rgb(var(--c-ac));
  font-size: 10px;
  text-transform: uppercase;
}
.part small,
.detail-empty {
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.workspace-loading,
.workspace-empty {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 26px 18px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.panel-empty {
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
}
.workspace-empty strong {
  color: rgb(var(--c-tx2));
  font-size: 13px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
@media (max-width: 768px) {
  .workspace-header {
    padding: 10px 14px;
  }
  .workspace-space-link {
    display: none;
  }
  .workspace-body {
    flex-direction: column;
  }
  .conversation-rail {
    width: 100%;
    max-height: 40vh;
    border-right: 0;
    border-bottom: 1px solid rgb(var(--c-line));
  }
  .conversation-list {
    max-height: 190px;
  }
  .message-layout {
    grid-template-columns: minmax(135px, 0.8fr) minmax(180px, 1.2fr);
  }
  .message-detail {
    padding: 14px;
  }
}
</style>
