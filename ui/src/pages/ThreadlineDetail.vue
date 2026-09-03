<template>
  <AppLayout :padded="false">
    <!-- Breadcrumb back to the list, then the actions for this conversation. -->
    <header
      class="flex h-[52px] flex-shrink-0 items-center gap-3 border-b border-line px-4 md:h-[56px] md:px-6"
    >
      <button
        type="button"
        class="flex flex-none items-center gap-[7px] text-[12.5px] text-ink-2 transition-colors hover:text-ink"
        @click="goBack"
      >
        <svg
          class="h-[15px] w-[15px]"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            d="M15 5l-7 7 7 7"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <span class="hidden sm:inline">{{ t('chats.title') }}</span>
      </button>
      <span class="hidden text-[12.5px] text-ink-4 sm:inline">/</span>
      <span class="min-w-0 flex-1 truncate text-[13px] text-ink-2 md:max-w-80">
        {{ headerTitle }}
      </span>

      <DetailActions
        class="ml-auto"
        :busy="isProcessing || deleting || retrying"
        :retrying="retrying"
        :shared="isShared"
        :share-busy="shareSaving || shareRevoking"
        @retry="handleRetryClick"
        @share="handleShareButtonClick"
        @share-settings="handleQuickShare"
        @delete="showDeleteConfirm = true"
      />
    </header>

    <div v-if="loading" class="flex flex-1 items-center justify-center">
      <span
        class="h-8 w-8 animate-spin rounded-full border-b-2 border-accent"
      ></span>
    </div>

    <div
      v-else-if="error"
      class="flex flex-1 flex-col items-center justify-center gap-2 text-center"
    >
      <p class="text-sm text-bad">{{ error }}</p>
      <button
        type="button"
        class="text-[12.5px] text-accent hover:underline"
        @click="loadThreadline"
      >
        {{ t('common.retry') }}
      </button>
    </div>

    <div
      v-else-if="threadline"
      class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4 md:flex-row md:gap-5 md:p-6"
    >
      <!-- What there is to read. -->
      <div class="flex min-w-0 flex-1 flex-col gap-4">
        <div class="flex flex-col gap-[9px]">
          <div class="flex flex-wrap items-center gap-[9px]">
            <span
              v-if="mergedCount"
              class="rounded-sm border border-accent px-1.5 py-0.5 font-mono text-[10px] text-accent opacity-85"
            >
              {{ t('chats.mergedBadge', { count: mergedCount }) }}
            </span>
            <span
              class="rounded-sm px-[7px] py-0.5 font-mono text-[10px]"
              :class="statusChipClass"
            >
              {{ statusLabel }}
            </span>
            <span
              v-if="isShared"
              class="rounded-sm border border-ok px-1.5 py-0.5 font-mono text-[10px] text-ok opacity-85"
            >
              {{ t('share.statusShared') }}
            </span>
          </div>

          <div v-if="!editingTitle" class="group flex items-start gap-2">
            <h1
              class="text-2xl font-semibold leading-[1.35] tracking-tight text-ink"
            >
              {{ headerTitle }}
            </h1>
            <button
              type="button"
              class="mt-2 flex-none text-ink-4 opacity-0 transition-opacity hover:text-ink-2 group-hover:opacity-100"
              :disabled="isProcessing"
              :aria-label="t('common.edit')"
              @click="startEditingTitle"
            >
              <svg
                class="h-3.5 w-3.5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <path
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </button>
          </div>

          <div v-else class="flex flex-col gap-1">
            <textarea
              ref="titleInputRef"
              v-model="editingTitleValue"
              rows="2"
              class="w-full resize-none rounded-md border border-accent bg-accent-soft px-3 py-2 text-2xl font-semibold leading-[1.35] text-ink focus:outline-none"
              :disabled="savingTitle"
            ></textarea>
            <p v-if="titleError" class="text-xs text-bad">{{ titleError }}</p>
            <div class="flex justify-end gap-2">
              <button
                type="button"
                class="text-[12.5px] text-ink-3 hover:text-ink"
                :disabled="savingTitle"
                @click="cancelEditingTitle"
              >
                {{ t('common.cancel') }}
              </button>
              <button
                type="button"
                class="text-[12.5px] text-accent hover:underline"
                :disabled="savingTitle"
                @click="saveTitle"
              >
                {{ t('common.save') }}
              </button>
            </div>
          </div>
        </div>

        <!-- The phone has no side column, so the sender, time and pipeline
             move up under the title where they stay visible. -->
        <div class="flex flex-col gap-2 md:hidden">
          <p class="font-mono text-[11px] text-ink-4">{{ mobileMetaLine }}</p>
          <div class="flex gap-1">
            <span
              v-for="index in 4"
              :key="index"
              class="h-[3px] flex-1 rounded-sm"
              :class="index <= stagesReached ? stageFillClass : 'bg-chip'"
            ></span>
          </div>
        </div>

        <!-- There is no room for a side column at 390px, so the sections
             become tabs and the panel below shows one at a time. -->
        <div class="flex gap-1.5 overflow-x-auto md:hidden">
          <button
            v-for="tab in mobileTabs"
            :key="tab.key"
            type="button"
            class="font-display flex-none rounded-md px-3 py-[7px] text-xs transition-colors"
            :class="
              mobileTab === tab.key
                ? 'bg-accent font-medium text-accent-on'
                : 'border border-line text-ink-2'
            "
            @click="mobileTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <template v-if="hasNewFormat">
          <PanelCard
            v-if="showsOnMobile('summary')"
            :title="t('chats.detail.coreTopic')"
          >
            <template #icon>
              <svg
                class="h-[15px] w-[15px] text-accent"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.9"
                aria-hidden="true"
              >
                <path d="M4 6h16M4 12h16M4 18h9" stroke-linecap="round" />
              </svg>
            </template>
            <template #actions>
              <button
                type="button"
                class="text-[11.5px] text-accent hover:underline disabled:opacity-50"
                :disabled="isProcessing || editingDetails"
                @click="openDetailsEditor"
              >
                {{ t('common.edit') }}
              </button>
              <button
                v-if="summaryData.details"
                type="button"
                class="text-[11.5px] text-ink-3 hover:text-ink"
                @click="copyContent(summaryData.details, 'details')"
              >
                {{
                  copiedStates.details ? t('common.copied') : t('common.copy')
                }}
              </button>
            </template>

            <InlineMarkdownEditor
              ref="detailsEditorRef"
              v-model="detailsValue"
              :label="t('chats.detail.coreTopic')"
              :placeholder="t('chats.detail.coreTopic')"
              :hint="t('common.markdownSupported')"
              :saving="savingDetails"
              :error="detailsError"
              :disabled="isProcessing"
              :show-edit-button="false"
              @save="saveDetails"
              @cancel="cancelEditingDetails"
            >
              <template #display>
                <MarkdownRenderer :content="summaryData.details" />
              </template>
            </InlineMarkdownEditor>
          </PanelCard>

          <PanelCard
            v-if="showsOnMobile('todos')"
            :title="t('todos.newFormat.todos')"
            :meta="todosMeta"
            flush
          >
            <template #icon>
              <svg
                class="h-[15px] w-[15px] text-accent"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.9"
                aria-hidden="true"
              >
                <rect x="3.5" y="3.5" width="17" height="17" rx="4" />
                <path
                  d="M8.5 12l2.5 2.5 4.5-5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </template>
            <template #actions>
              <button
                type="button"
                class="text-[11.5px] text-accent hover:underline disabled:opacity-50"
                :disabled="
                  !!tempNewTodo || savingNewTodo || editingTodoIds.size > 0
                "
                @click="handleAddTodo"
              >
                {{ t('todos.add') }}
              </button>
            </template>

            <TransitionGroup name="todo-list" tag="div">
              <TodoItem
                v-if="tempNewTodo"
                :key="tempNewTodo.id"
                :todo="tempNewTodo"
                :loading="savingNewTodo"
                :email-message-id="threadline?.id"
                :is-new="true"
                @toggle="() => {}"
                @save="saveNewTodo"
                @delete="() => {}"
                @cancel-new="cancelNewTodo"
                @editing-change="
                  (editing) => handleTodoEditingChange(tempNewTodo.id, editing)
                "
              />
              <TodoItem
                v-for="todo in threadlineTodos"
                :key="todo.id"
                :todo="todo"
                :loading="todoLoading[todo.id]"
                :email-message-id="threadline?.id"
                @toggle="handleToggleTodo"
                @save="handleSaveTodoInline"
                @delete="handleDeleteTodo"
                @editing-change="
                  (editing) => handleTodoEditingChange(todo.id, editing)
                "
              />
            </TransitionGroup>
            <p
              v-if="!threadlineTodos.length && !tempNewTodo"
              class="px-4 py-8 text-center text-sm italic text-ink-3"
            >
              {{ t('todos.noTodos') }}
            </p>
          </PanelCard>

          <PanelCard
            v-if="showsOnMobile('summary')"
            :title="t('todos.newFormat.keyProcess')"
          >
            <template #icon>
              <svg
                class="h-[15px] w-[15px] text-accent"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.9"
                aria-hidden="true"
              >
                <path
                  d="M12 3v18M12 3l-5 5M12 3l5 5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </template>
            <template #actions>
              <button
                type="button"
                class="text-[11.5px] text-accent hover:underline disabled:opacity-50"
                :disabled="isProcessing || editingKeyProcess"
                @click="openKeyProcessEditor"
              >
                {{ t('common.edit') }}
              </button>
              <button
                v-if="summaryData.key_process?.length"
                type="button"
                class="text-[11.5px] text-ink-3 hover:text-ink"
                @click="copyKeyProcess"
              >
                {{
                  copiedStates.keyProcess
                    ? t('common.copied')
                    : t('common.copy')
                }}
              </button>
            </template>

            <InlineArrayEditor
              ref="keyProcessEditorRef"
              v-model="keyProcessValue"
              :label="t('todos.newFormat.keyProcess')"
              :placeholder="t('todos.newFormat.keyProcessPlaceholder')"
              :hint="t('todos.newFormat.keyProcessHint')"
              :saving="savingKeyProcess"
              :error="keyProcessError"
              :disabled="isProcessing"
              :show-edit-button="false"
              @save="saveKeyProcess"
              @cancel="cancelEditingKeyProcess"
            />
          </PanelCard>
        </template>

        <PanelCard
          v-else-if="showsOnMobile('summary')"
          :title="t('chats.aiSummary')"
        >
          <template #actions>
            <button
              v-if="threadline.summary_content"
              type="button"
              class="text-[11.5px] text-ink-3 hover:text-ink"
              @click="copyContent(threadline.summary_content, 'summary')"
            >
              {{ copiedStates.summary ? t('common.copied') : t('common.copy') }}
            </button>
          </template>
          <MarkdownRenderer
            v-if="threadline.summary_content"
            :content="threadline.summary_content"
          />
          <p v-else class="py-8 text-center text-sm italic text-ink-3">
            {{ t('chats.noSummary') }}
          </p>
        </PanelCard>

        <ThreadlineAttachments
          v-if="threadline.attachments?.length && showsOnMobile('files')"
          :attachments="threadline.attachments"
        />

        <!-- The raw material, folded away: it is there to check against, not
             to read first. -->
        <div
          v-if="showsOnMobile('raw')"
          class="flex flex-col gap-2.5 md:flex-row"
        >
          <DetailDisclosure
            v-if="originalEmailContent"
            class="flex-1"
            :label="t('chats.detail.originalEmails')"
          >
            <pre
              class="whitespace-pre-wrap break-words font-sans text-[13px] leading-[1.7] text-ink-2"
              >{{ originalEmailContent }}</pre
            >
          </DetailDisclosure>
          <DetailDisclosure
            v-if="threadline.llm_content"
            class="flex-1"
            :label="t('chats.detail.aiOutput')"
          >
            <MarkdownRenderer :content="threadline.llm_content" />
          </DetailDisclosure>
        </div>
      </div>

      <!-- What there is to look up. -->
      <aside
        v-if="showsOnMobile('info')"
        class="flex w-full flex-col gap-3.5 md:w-80 md:flex-none"
      >
        <DetailStatusCard
          :status="threadline.status"
          :percent="Math.round(displayedProgressPercent)"
        />
        <DetailInfoCard
          :threadline="threadline"
          :format-date="formatDate"
          :saving="isSaving"
          @change="onChipsChange"
          @save="onChipsSave"
        />
        <DetailTagsCard
          :threadline="threadline"
          :saving="isSaving('keywords')"
          @change="(value) => onChipsChange('keywords', value)"
          @save="(value) => onChipsSave('keywords', value)"
        />
        <DetailRelayCard
          v-if="getRelayDeliveries(threadline).length"
          :threadline="threadline"
          :format-date="formatDate"
        />
        <DetailMergeCard
          v-if="threadline.merged_children?.length"
          :threadline="threadline"
          :format-date="formatDate"
        />
      </aside>
    </div>

    <MetadataFieldEditor
      :show="showEditor"
      :field-key="editorKey"
      :value="editorValue"
      @cancel="closeEditor"
      @save="saveEditor"
    />
    <RetryDialog
      :show="showRetryDialog"
      :status="threadline?.status"
      @close="showRetryDialog = false"
      @confirm="handleRetry"
    />
    <ConfirmDialog
      :show="showDeleteConfirm"
      :title="t('common.delete')"
      :message="t('chats.detail.deleteConfirm')"
      variant="danger"
      :confirm-text="t('common.delete')"
      :loading="deleting"
      @close="showDeleteConfirm = false"
      @confirm="confirmDelete"
    />
    <ThreadlineShareModal :share="share" :share-status="shareStatus" />
  </AppLayout>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MetadataFieldEditor from '@/components/MetadataFieldEditor.vue'
import RetryDialog from '@/components/RetryDialog.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import TodoItem from '@/components/TodoItem.vue'
import InlineMarkdownEditor from '@/components/InlineMarkdownEditor.vue'
import InlineArrayEditor from '@/components/InlineArrayEditor.vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import MarkdownRenderer from '@/components/ui/MarkdownRenderer.vue'
import ThreadlineAttachments from '@/components/threadline/ThreadlineAttachments.vue'
import DetailActions from '@/components/threadline/detail/DetailActions.vue'
import DetailDisclosure from '@/components/threadline/detail/DetailDisclosure.vue'
import DetailInfoCard from '@/components/threadline/detail/DetailInfoCard.vue'
import DetailMergeCard from '@/components/threadline/detail/DetailMergeCard.vue'
import DetailRelayCard from '@/components/threadline/detail/DetailRelayCard.vue'
import DetailStatusCard from '@/components/threadline/detail/DetailStatusCard.vue'
import DetailTagsCard from '@/components/threadline/detail/DetailTagsCard.vue'
import ThreadlineShareModal from '@/components/threadline/detail/ThreadlineShareModal.vue'
import { useThreadline } from '@/composables/useThreadline'
import { useThreadlinePolling } from '@/composables/useThreadlinePolling'
import { useThreadlineShare } from '@/composables/useThreadlineShare'
import { useThreadlineTodos } from '@/composables/useThreadlineTodos'
import { useThreadlineMetadata } from '@/composables/useThreadlineMetadata'
import { useThreadlineContent } from '@/composables/useThreadlineContent'
import { useRelayDeliveries } from '@/composables/useRelayDeliveries'

const route = useRoute()
const { t } = useI18n()
const { getRelayDeliveries } = useRelayDeliveries()

const threadline = ref(null)
const polling = useThreadlinePolling(threadline, route)

const {
  loading,
  error,
  deleting,
  showDeleteConfirm,
  shareStatus,
  isProcessing,
  hasNewFormat,
  summaryData,
  formatDate,
  loadThreadline,
  confirmDelete,
  goBack,
  handleClickOutside
} = useThreadline(route, polling.startPolling, threadline)

const share = useThreadlineShare(threadline, route)
const todos = useThreadlineTodos(threadline)
const metadata = useThreadlineMetadata(threadline, route)
const content = useThreadlineContent(threadline, route, () => summaryData.value)

const { shareSaving, shareRevoking, handleQuickShare, handleStopSharing } =
  share
const { showEditor, editorKey, editorValue, closeEditor, saveEditor } = metadata
const { onChipsChange, onChipsSave, isSaving } = metadata

const {
  threadlineTodos,
  todoLoading,
  tempNewTodo,
  savingNewTodo,
  editingTodoIds,
  handleAddTodo,
  saveNewTodo,
  cancelNewTodo,
  handleTodoEditingChange,
  handleSaveTodoInline,
  handleToggleTodo,
  handleDeleteTodo
} = todos

const {
  copiedStates,
  detailsEditorRef,
  keyProcessEditorRef,
  editingTitle,
  editingTitleValue,
  savingTitle,
  titleError,
  titleInputRef,
  startEditingTitle,
  cancelEditingTitle,
  saveTitle,
  detailsValue,
  savingDetails,
  detailsError,
  editingDetails,
  cancelEditingDetails,
  saveDetails,
  keyProcessValue,
  editingKeyProcess,
  savingKeyProcess,
  keyProcessError,
  cancelEditingKeyProcess,
  saveKeyProcess,
  copyContent,
  openDetailsEditor,
  openKeyProcessEditor,
  copyKeyProcess
} = content

const { retrying, showRetryDialog, handleRetry } = polling
const handleRetryClick = () =>
  polling.handleRetryClick(isProcessing.value, deleting.value)

const mobileMetaLine = computed(() => {
  const parts = [
    threadline.value?.sender,
    formatDate(threadline.value?.received_at || threadline.value?.created_at)
  ]
  const files = threadline.value?.attachments?.length
  if (files) {
    parts.push(t('chats.attachmentsShort', { count: files }))
  }
  return parts.filter(Boolean).join(' · ')
})

const stagesReached = computed(() => {
  const status = threadline.value?.status
  if (status === 'success') return 4
  if (status === 'failed') return 1
  if (status === 'processing' || status === 'retrying') {
    return Math.min(3, 1 + Math.floor(displayedProgressPercent.value / 40))
  }
  return 1
})
const stageFillClass = computed(() => {
  const status = threadline.value?.status
  if (status === 'failed') return 'bg-bad'
  return status === 'success' ? 'bg-ok' : 'bg-warn'
})

const mobileTab = ref('summary')
const mobileTabs = computed(() => [
  { key: 'summary', label: t('chats.detail.tabSummary') },
  {
    key: 'todos',
    label: `${t('chats.detail.tabTodos')} ${threadlineTodos.value.length}`
  },
  {
    key: 'files',
    label: `${t('chats.detail.tabFiles')} ${threadline.value?.attachments?.length || 0}`
  },
  { key: 'info', label: t('chats.detail.tabInfo') },
  { key: 'raw', label: t('chats.detail.tabRaw') }
])
// Desktop shows every section at once; only the phone narrows to one.
const isNarrow = ref(false)
const showsOnMobile = (key) => !isNarrow.value || mobileTab.value === key

const headerTitle = computed(
  () =>
    threadline.value?.summary_title ||
    threadline.value?.subject ||
    t('common.noSubject')
)
const mergedCount = computed(
  () => threadline.value?.merged_children?.length || 0
)
const isShared = computed(
  () => Boolean(shareStatus.value?.is_active) && !shareStatus.value?.is_expired
)
const todosMeta = computed(() =>
  t('chats.detail.todosMeta', {
    total: threadlineTodos.value.length,
    done: threadlineTodos.value.filter((todo) => todo.is_completed).length
  })
)

const STATUS_LABELS = {
  success: 'chats.stateCompleted',
  processing: 'chats.stateProcessing',
  retrying: 'chats.stateProcessing',
  failed: 'chats.stateFailed',
  fetched: 'chats.statePending'
}
const statusLabel = computed(() =>
  t(STATUS_LABELS[threadline.value?.status] || 'common.status.unknown')
)
const statusChipClass = computed(
  () =>
    ({
      success: 'bg-ok-soft text-ok',
      processing: 'bg-warn-soft text-warn',
      retrying: 'bg-warn-soft text-warn',
      failed: 'bg-bad-soft text-bad',
      fetched: 'bg-chip text-ink-2'
    })[threadline.value?.status] || 'bg-chip text-ink-2'
)

// The side panel's four bars follow the live percent while work is running.
const displayedProgressPercent = computed(() => {
  const snapshot =
    threadline.value?.processing_progress ||
    threadline.value?.metadata?.processing_progress
  const percent = Number(snapshot?.percent ?? snapshot?.progress_percent)
  return Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0
})

const normalizeHtmlContent = (value) => {
  if (!value) return ''
  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') {
    return value
  }

  try {
    const doc = new DOMParser().parseFromString(value, 'text/html')
    return (doc.body?.innerText || doc.body?.textContent || '').trim()
  } catch {
    return value
  }
}

const originalEmailContent = computed(() => {
  const text = threadline.value?.text_content?.trim()
  if (text) return text

  const html = threadline.value?.html_content?.trim()
  return html ? normalizeHtmlContent(html) : ''
})

// Sharing is a toggle in the header; the dialog behind "…" is where the link,
// password and expiry live.
const handleShareButtonClick = async () => {
  if (!threadline.value || shareSaving.value || shareRevoking.value) return

  if (isShared.value) {
    handleStopSharing()
    return
  }

  if (isProcessing.value || deleting.value || retrying.value) return

  await handleQuickShare()
}

const NARROW = window.matchMedia('(max-width: 767px)')
const syncNarrow = (event) => {
  isNarrow.value = event.matches
}

onMounted(() => {
  isNarrow.value = NARROW.matches
  NARROW.addEventListener('change', syncNarrow)
  loadThreadline()
  document.addEventListener('click', handleClickOutside)
})

watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) {
      polling.resetRetryState()
      loadThreadline()
    }
  }
)

onUnmounted(() => {
  polling.resetRetryState()
  NARROW.removeEventListener('change', syncNarrow)
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.todo-list-enter-active,
.todo-list-leave-active {
  transition: all 0.3s ease;
}

.todo-list-enter-from,
.todo-list-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.todo-list-move {
  transition: transform 0.3s ease;
}
</style>
