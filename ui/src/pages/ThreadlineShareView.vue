<template>
  <div class="flex min-h-screen flex-col bg-app-sub">
    <ShareHeader />
    <main class="flex flex-1 justify-center px-4 py-7 md:px-10">
      <div class="flex w-full max-w-[860px] flex-col gap-4">
        <BaseCard
          v-if="loading"
          class="bg-gradient-to-b from-white via-white to-accent-soft/40 border border-accent shadow-sm"
        >
          <div class="flex flex-col items-center gap-4 py-8 text-center">
            <div class="relative">
              <div
                class="h-12 w-12 rounded-full bg-accent-soft flex items-center justify-center text-accent shadow-inner"
              >
                <svg
                  class="w-6 h-6 animate-spin"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M4 12a8 8 0 018-8"
                  />
                </svg>
              </div>
            </div>
            <div class="space-y-1">
              <p class="text-base font-semibold text-ink">
                {{ t('share.viewLoading') }}
              </p>
              <p class="text-sm text-ink-3">
                {{ t('share.viewLoadingDescription') }}
              </p>
            </div>
          </div>
        </BaseCard>

        <BaseCard v-else-if="error" class="max-w-md mx-auto">
          <div class="space-y-6 py-6 text-center">
            <div
              class="mx-auto w-16 h-16 bg-bad-soft rounded-full flex items-center justify-center shadow-inner"
            >
              <svg
                class="w-7 h-7 text-bad"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>

            <div class="space-y-2 px-4">
              <h2 class="text-lg font-semibold text-ink">
                {{ t('share.linkExpired') }}
              </h2>
              <p class="text-sm text-ink-3 leading-relaxed">
                {{ error || t('share.viewExpired') }}
              </p>
            </div>

            <div class="flex justify-center">
              <BaseButton variant="primary" size="md" @click="goHome">
                {{ t('share.backToHome') }}
              </BaseButton>
            </div>
          </div>
        </BaseCard>

        <BaseCard
          v-else-if="requiresPassword && !threadline"
          class="max-w-sm mx-auto"
        >
          <div class="space-y-5 py-4">
            <!-- Icon and Title -->
            <div class="text-center space-y-2">
              <div
                class="mx-auto w-12 h-12 bg-accent-soft rounded-full flex items-center justify-center"
              >
                <svg
                  class="w-6 h-6 text-accent"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                  />
                </svg>
              </div>
              <div class="space-y-1">
                <h2 class="text-lg font-semibold text-ink">
                  {{ t('share.requiresPassword') }}
                </h2>
                <p class="text-xs text-ink-3">
                  {{ t('share.passwordPrompt') }}
                </p>
              </div>
            </div>

            <!-- Password Input -->
            <div class="space-y-3">
              <input
                v-model="passwordInput"
                type="password"
                maxlength="6"
                minlength="6"
                inputmode="numeric"
                pattern="[0-9]*"
                autocomplete="off"
                class="w-full rounded-xl border px-4 py-3 text-center text-lg font-medium tracking-[0.15em] bg-panel text-ink shadow-sm transition-all focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none placeholder:text-ink-4 placeholder:font-normal"
                :class="
                  passwordError
                    ? 'border-bad ring-1 ring-bad'
                    : 'border-line hover:border-line'
                "
                :placeholder="t('share.passwordPlaceholder')"
                @keyup.enter="submitPassword"
                @input="passwordError = ''"
                ref="passwordInputRef"
              />
              <p
                v-if="passwordError"
                class="text-xs text-bad text-center flex items-center justify-center gap-1"
              >
                <svg
                  class="w-3.5 h-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                {{ passwordError }}
              </p>
            </div>

            <!-- Submit Button -->
            <BaseButton
              variant="primary"
              :loading="verifying"
              block
              size="md"
              @click="submitPassword"
              :disabled="passwordInput.trim().length !== 6"
              class="font-medium"
            >
              {{ t('share.submitPassword') }}
            </BaseButton>
          </div>
        </BaseCard>

        <!-- Threadline Content - Reusing Detail Page Structure -->
        <div v-else-if="threadline" class="space-y-6">
          <div
            class="flex items-center gap-[11px] rounded-[9px] border border-line border-l-[3px] border-l-accent bg-panel px-[15px] py-[11px]"
          >
            <svg
              class="h-4 w-4 flex-none text-accent"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.9"
              aria-hidden="true"
            >
              <path
                d="M4 12v7a1 1 0 001 1h14a1 1 0 001-1v-7M12 3v12M8 7l4-4 4 4"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            <span class="text-[calc(12.5px*var(--fs))] text-ink-2">
              {{ t('share.readOnlyNotice') }}
            </span>
            <span
              v-if="shareExpiresAt"
              class="ml-auto font-mono text-[calc(11px*var(--fs))] text-ink-4"
            >
              {{
                t('share.expiresOn', {
                  date: formatShareDate(shareExpiresAt)
                })
              }}
            </span>
          </div>

          <div
            class="flex flex-col gap-3.5 rounded-[11px] border border-line bg-panel px-7 py-[26px]"
          >
            <h1
              class="text-[calc(25px*var(--fs))] font-semibold leading-[1.4] tracking-tight text-ink"
            >
              {{
                threadline.summary_title ||
                threadline.subject ||
                t('common.noSubject')
              }}
            </h1>
            <div
              class="flex flex-wrap items-center gap-x-3.5 gap-y-1.5 font-mono text-[calc(11.5px*var(--fs))] text-ink-4"
            >
              <span>
                {{
                  formatShareDate(
                    threadline.received_at || threadline.created_at
                  )
                }}
              </span>
              <template v-for="fact in metaFacts" :key="fact">
                <span>·</span>
                <span>{{ fact }}</span>
              </template>
            </div>
            <div v-if="shareTags.length" class="flex flex-wrap gap-1.5">
              <span
                v-for="tag in shareTags"
                :key="tag"
                class="rounded-sm bg-chip px-[9px] py-[3px] font-mono text-[calc(10.5px*var(--fs))] text-ink-2"
              >
                {{ tag }}
              </span>
            </div>
          </div>

          <!-- Details Section (New Format) -->
          <PanelCard
            v-if="hasNewFormat && summaryData.details"
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
                <path
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </template>
            <MarkdownRenderer :content="summaryData.details" />
          </PanelCard>

          <!-- TODOs Section -->
          <PanelCard
            v-if="threadlineTodos.length > 0"
            :title="t('todos.newFormat.todos')"
            :meta="String(threadlineTodos.length)"
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
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </template>
            <TransitionGroup name="todo-list" tag="div" class="space-y-2">
              <TodoItem
                v-for="todo in threadlineTodos"
                :key="todo.id"
                :todo="todo"
                :loading="false"
                :email-message-id="threadline?.id"
                :read-only="true"
                @toggle="() => {}"
                @save="() => {}"
                @delete="() => {}"
                @editing-change="() => {}"
              />
            </TransitionGroup>
          </PanelCard>

          <!-- Key Process Section -->
          <PanelCard
            v-if="
              hasNewFormat &&
              summaryData.key_process &&
              summaryData.key_process.length > 0
            "
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
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </template>
            <ol class="flex flex-col gap-[11px]">
              <li
                v-for="(item, index) in summaryData.key_process"
                :key="index"
                class="flex items-start gap-[11px]"
              >
                <span
                  class="flex h-[18px] w-[18px] flex-none items-center justify-center rounded-full border border-line font-mono text-[calc(10px*var(--fs))] text-ink-3"
                >
                  {{ index + 1 }}
                </span>
                <span class="text-[calc(13px*var(--fs))] leading-[1.6] text-ink-2">
                  {{ item }}
                </span>
              </li>
            </ol>
          </PanelCard>

          <!-- Conversation Records (LLM Content) -->
          <PanelCard
            v-if="
              threadline.llm_content ||
              (!hasNewFormat && threadline.summary_content)
            "
            :title="t('chats.processedContent')"
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
                  d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </template>
            <div v-if="threadline.llm_content">
              <MarkdownRenderer :content="threadline.llm_content" />
            </div>
            <div v-else-if="threadline.summary_content">
              <MarkdownRenderer :content="threadline.summary_content" />
            </div>
          </PanelCard>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePreferencesStore } from '@/store/preferences'
import { formatDate } from '@/utils/timezone'
import { chatApi } from '@/api/chat'
import ShareHeader from '@/components/layout/ShareHeader.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import MarkdownRenderer from '@/components/ui/MarkdownRenderer.vue'
import TodoItem from '@/components/TodoItem.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const preferences = usePreferencesStore()

const loading = ref(true)
const error = ref('')
const shareExpiresAt = ref(null)
const requiresPassword = ref(false)
const verifying = ref(false)
const threadline = ref(null)
const passwordInput = ref('')
const passwordError = ref('')
const passwordInputRef = ref(null)

// Copy states
const MAX_RETRIES = 5
const RETRY_DELAY = 2000

const token = computed(() => route.params.token)

// Check if threadline has new format
const hasNewFormat = computed(() => {
  if (!threadline.value) return false
  return !!(
    threadline.value.summary_data &&
    (threadline.value.summary_data.details ||
      threadline.value.summary_data.key_process)
  )
})

// Extract summary data
const summaryData = computed(() => {
  if (!threadline.value || !threadline.value.summary_data) {
    return {}
  }
  const data = threadline.value.summary_data
  if (typeof data === 'string') {
    try {
      return JSON.parse(data)
    } catch (err) {
      console.error('Failed to parse summary data:', err)
      return {}
    }
  }
  return data
})

// Extract todos
const threadlineTodos = computed(() => {
  if (!threadline.value || !threadline.value.todos) {
    return []
  }
  return threadline.value.todos
})

const metadataInfo = computed(() => threadline.value?.metadata || null)

const normalizeMetadataArray = (value) => {
  if (!value) {
    return []
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === 'string' ? item.trim() : ''))
      .filter((item) => item && item.length > 0)
  }
  if (typeof value === 'string') {
    return value
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
  }
  return []
}

const metadataCategory = computed(() => {
  const value = metadataInfo.value?.category
  if (typeof value === 'string') {
    return value.trim()
  }
  return ''
})

const metadataParticipants = computed(() =>
  normalizeMetadataArray(metadataInfo.value?.participants)
)
const metadataTags = computed(() =>
  normalizeMetadataArray(metadataInfo.value?.keywords)
)
// The title block carries the facts as one line, the way the canvas reads
// them: category, then participants, then anything else worth naming.
const metaFacts = computed(() => {
  const facts = []
  if (metadataCategory.value) facts.push(metadataCategory.value)
  if (metadataParticipants.value.length) {
    facts.push(
      t('share.participantCount', {
        count: metadataParticipants.value.length
      })
    )
  }
  return facts
})

const shareTags = computed(() => metadataTags.value)

const formatShareDate = (dateString) => {
  if (!dateString) {
    return t('common.noData')
  }
  try {
    return formatDate(
      dateString,
      preferences.currentTimezone,
      'yyyy-MM-dd HH:mm',
      preferences.currentLanguage
    )
  } catch (err) {
    console.error('Failed to format date:', err)
    return dateString
  }
}

const normalizeSummaryData = (data) => {
  if (!data) {
    return {}
  }
  if (typeof data === 'string') {
    try {
      return JSON.parse(data)
    } catch (err) {
      console.error('Failed to parse summary data:', err)
      return {}
    }
  }
  return data
}

const prepareThreadline = (data) => {
  if (!data) {
    return null
  }
  return {
    ...data,
    summary_data: normalizeSummaryData(data.summary_data),
    todos: data.todos || []
  }
}

const loadShare = async (retryCount = 0) => {
  loading.value = true
  error.value = ''
  threadline.value = null
  requiresPassword.value = false

  try {
    const response = await chatApi.getPublicShare(token.value)
    const data = response.data.data || response.data
    requiresPassword.value = data.requires_password
    shareExpiresAt.value = data.share?.expires_at || null
    if (!data.requires_password) {
      threadline.value = prepareThreadline(data.threadline)
    }
    loading.value = false
  } catch (err) {
    const status = err.response?.status
    const isGone = status === 410
    const isNotFound = status === 404

    // Don't retry for permanent errors (410 Gone, 404 Not Found)
    if (isGone || isNotFound) {
      const errorMessage = err.response?.data?.message || ''
      // Translate common backend error messages
      if (errorMessage.includes('expired or is inactive')) {
        error.value = t('share.linkExpiredOrInactive')
      } else if (
        errorMessage &&
        errorMessage.length > 10 &&
        !errorMessage.toLowerCase().includes('failed')
      ) {
        // Only use backend message if it's meaningful and not just "failed"
        error.value = errorMessage
      } else {
        error.value = t('share.viewExpired')
      }
      loading.value = false
      return
    }

    console.error(
      `Failed to load share (attempt ${retryCount + 1}/${MAX_RETRIES}):`,
      err
    )

    // Only retry for transient errors (network issues, 500, etc.)
    if (retryCount < MAX_RETRIES - 1) {
      const delay = RETRY_DELAY * (retryCount + 1)
      console.log(`Retrying in ${delay}ms...`)
      setTimeout(() => {
        loadShare(retryCount + 1)
      }, delay)
    } else {
      const errorMessage = err.response?.data?.message || ''
      // Translate common backend error messages
      if (errorMessage.includes('expired or is inactive')) {
        error.value = t('share.linkExpiredOrInactive')
      } else if (
        errorMessage &&
        errorMessage.length > 10 &&
        !errorMessage.toLowerCase().includes('failed')
      ) {
        // Only use backend message if it's meaningful and not just "failed"
        error.value = errorMessage
      } else {
        error.value = t('share.viewExpired')
      }
      loading.value = false
    }
  }
}

const submitPassword = async (retryCount = 0) => {
  passwordError.value = ''
  const trimmedPassword = passwordInput.value.trim()
  if (!trimmedPassword || !/^\d{6}$/.test(trimmedPassword)) {
    passwordError.value = t('share.passwordRequired')
    return
  }

  verifying.value = true
  error.value = ''

  try {
    const response = await chatApi.verifyPublicShare(token.value, {
      password: passwordInput.value.trim()
    })
    const data = response.data.data || response.data
    requiresPassword.value = false
    threadline.value = prepareThreadline(data.threadline)
    verifying.value = false
  } catch (err) {
    const status = err.response?.status
    const isGone = status === 410
    const isNotFound = status === 404
    const isForbidden = status === 403

    // Handle password errors - don't retry
    if (isForbidden) {
      passwordError.value = t('share.invalidPassword')
      passwordInput.value = ''
      verifying.value = false
      await nextTick()
      if (passwordInputRef.value) {
        passwordInputRef.value.focus()
      }
      return
    }

    // Don't retry for permanent errors (410 Gone, 404 Not Found)
    if (isGone || isNotFound) {
      const errorMessage = err.response?.data?.message || ''
      // Translate common backend error messages
      if (errorMessage.includes('expired or is inactive')) {
        error.value = t('share.linkExpiredOrInactive')
      } else if (
        errorMessage &&
        errorMessage.length > 10 &&
        !errorMessage.toLowerCase().includes('failed')
      ) {
        // Only use backend message if it's meaningful and not just "failed"
        error.value = errorMessage
      } else {
        error.value = t('share.viewExpired')
      }
      verifying.value = false
      return
    }

    // Only retry for transient errors (network issues, 500, etc.)
    if (retryCount < MAX_RETRIES - 1) {
      const delay = RETRY_DELAY * (retryCount + 1)
      console.log(`Password verification failed, retrying in ${delay}ms...`)
      setTimeout(() => {
        submitPassword(retryCount + 1)
      }, delay)
    } else {
      const errorMessage = err.response?.data?.message || ''
      // Translate common backend error messages
      if (errorMessage.includes('expired or is inactive')) {
        error.value = t('share.linkExpiredOrInactive')
      } else if (
        errorMessage &&
        errorMessage.length > 10 &&
        !errorMessage.toLowerCase().includes('failed')
      ) {
        // Only use backend message if it's meaningful and not just "failed"
        error.value = errorMessage
      } else {
        error.value = t('share.viewExpired')
      }
      verifying.value = false
    }
  }
}

const goHome = () => {
  router.push('/chats')
}

const focusPasswordInput = async () => {
  await nextTick()
  if (passwordInputRef.value && requiresPassword.value) {
    setTimeout(() => {
      if (passwordInputRef.value) {
        passwordInputRef.value.focus()
      }
    }, 100)
  }
}

watch(requiresPassword, (newVal) => {
  if (newVal) {
    focusPasswordInput()
  }
})

onMounted(() => {
  loadShare()
})

watch(token, (newToken, oldToken) => {
  if (newToken && newToken !== oldToken) {
    loadShare()
  }
})
</script>
