<template>
  <AppLayout :padded="false">
    <div class="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row">
      <div
        class="flex flex-shrink-0 flex-col md:w-[236px] md:border-r md:border-line"
      >
        <PageHeader
          :title="t('settings.title')"
          gutter="sm"
          class="md:border-r-0"
        />
        <SettingsNav v-model="activeSettingsTab" :sections="settingsTabs" />
      </div>

      <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <!-- Each section names itself and carries its own save, so a change
             here never looks like it might have saved something over there. -->
        <div
          class="flex h-14 flex-shrink-0 items-center gap-3 border-b border-line px-4 md:px-7"
        >
          <span class="text-[14.5px] font-semibold text-ink">
            {{ activeSection.label }}
          </span>
          <span class="hidden text-xs text-ink-3 lg:block">
            {{ activeSection.description }}
          </span>
        </div>

        <div
          v-if="loadingSettings"
          class="border-b border-line bg-app-sub px-4 py-2 text-sm text-ink-2 md:px-7"
        >
          {{ t('settings.loadingSettings') }}
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto p-4 md:p-7">
          <div
            v-if="activeSettingsTab === 'account'"
            class="flex flex-col gap-[22px]"
          >
            <div class="flex items-center gap-4 pb-1">
              <span
                :class="avatarBgColor"
                class="flex h-14 w-14 flex-none items-center justify-center rounded-full text-[22px] text-accent-on"
              >
                {{ userInitials }}
              </span>
              <span class="flex min-w-0 flex-col gap-1">
                <span
                  class="font-display truncate text-[17px] font-semibold text-ink"
                >
                  {{ displayName }}
                </span>
                <span class="truncate font-mono text-xs text-ink-3">
                  {{ userStore.userInfo?.email || '' }}
                </span>
              </span>
            </div>

            <div class="h-px bg-line"></div>

            <SettingsRow
              :title="t('settings.aiEmail')"
              :description="t('settings.aiEmailDesc')"
            >
              <div
                v-if="loadingSettings"
                class="h-[52px] animate-pulse rounded-[9px] bg-chip"
              ></div>
              <template v-else-if="hasDisplayedAiEmail">
                <div
                  class="flex items-center gap-[11px] rounded-[9px] border border-line border-l-[3px] border-l-accent bg-panel-sub px-[15px] py-3"
                >
                  <svg
                    class="h-[17px] w-[17px] flex-none text-accent"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.9"
                    aria-hidden="true"
                  >
                    <rect x="2.5" y="4.5" width="19" height="15" rx="2.5" />
                    <path
                      d="M3 7l9 6 9-6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                  <span
                    class="min-w-0 flex-1 truncate font-mono text-[13.5px] text-ink"
                  >
                    {{ displayedAiEmail }}
                  </span>
                  <span
                    class="flex-none rounded-sm bg-chip px-[7px] py-0.5 font-mono text-[10.5px] text-ink-3"
                  >
                    {{ t('settings.systemAssigned') }}
                  </span>
                </div>
                <p class="text-[11.5px] text-ink-3">
                  {{ t('settings.aiEmailInUse') }}
                  <button
                    type="button"
                    class="text-accent hover:underline"
                    @click="goToEmailSettings"
                  >
                    {{ t('settings.goToEmailSettings') }}
                  </button>
                </p>
              </template>
              <div
                v-else
                class="rounded-[9px] border border-warn bg-warn-soft p-3"
              >
                <p class="text-sm font-medium text-warn">
                  {{ t('settings.noAiEmailConfigured') }}
                </p>
                <p class="mt-1 text-xs leading-5 text-warn">
                  {{ t('settings.noAiEmailHint') }}
                </p>
                <button
                  type="button"
                  class="mt-2 text-xs font-medium text-warn hover:underline"
                  @click="goToEmailSettings"
                >
                  {{ t('settings.goToEmailSettings') }}
                </button>
              </div>
            </SettingsRow>

            <div class="h-px bg-line"></div>

            <SettingsRow
              :title="t('settings.authMethod')"
              :description="t('settings.authMethodDesc')"
            >
              <div
                class="flex items-center gap-[11px] rounded-[9px] border border-line bg-panel px-[15px] py-3"
              >
                <svg
                  class="h-[17px] w-[17px] flex-none"
                  :class="isOauth ? 'text-ok' : 'text-accent'"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.9"
                  aria-hidden="true"
                >
                  <path
                    v-if="isOauth"
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                  <path
                    v-else
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                <span class="flex min-w-0 flex-1 flex-col gap-px">
                  <span class="text-[13px] text-ink">
                    {{
                      isOauth
                        ? t('settings.oauthAuth')
                        : t('settings.emailAuth')
                    }}
                  </span>
                  <span
                    v-if="isOauth && authInfo?.login_identifier"
                    class="truncate font-mono text-[11px] text-ink-3"
                  >
                    {{ authInfo.provider }} · {{ authInfo.login_identifier }}
                  </span>
                </span>
                <BaseButton
                  v-if="authInfo?.can_change_password"
                  variant="secondary"
                  size="sm"
                  class="flex-none"
                  @click="showPasswordResetConfirm = true"
                >
                  {{ t('settings.resetPassword') }}
                </BaseButton>
              </div>

              <p
                v-if="!authInfo?.can_change_password"
                class="text-[11.5px] leading-[1.6] text-ink-3"
              >
                {{ t('settings.oauthPasswordChangeInfo') }}
              </p>

              <p v-if="resetEmailSent" class="text-[11.5px] text-ok">
                {{ t('settings.passwordResetEmailSent') }} ·
                {{ t('settings.passwordResetEmailSentDesc') }}
              </p>
              <p v-if="resetEmailError" class="text-[11.5px] text-bad">
                {{ resetEmailError }}
              </p>
            </SettingsRow>
          </div>

          <div v-else-if="activeSettingsTab === 'message'" class="space-y-6">
            <div class="space-y-5">
              <div class="flex flex-col gap-3 md:flex-row md:gap-7">
                <div class="md:w-44 md:flex-none">
                  <label class="block text-sm font-medium text-ink-2 mb-1">
                    {{ t('settings.language') }}
                  </label>
                  <p class="text-xs text-ink-3">
                    {{ t('settings.languageDesc') }}
                  </p>
                </div>
                <div class="min-w-0 md:max-w-[640px] md:flex-1">
                  <select
                    v-model="preferenceForm.language"
                    class="block w-full pl-3 pr-10 py-2 text-sm border-line bg-panel focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent rounded-md shadow-sm appearance-none cursor-pointer hover:border-line transition-colors"
                  >
                    <option value="en">
                      {{ t('settings.languages.en') }}
                    </option>
                    <option value="zh-CN">
                      {{ t('settings.languages.zh-CN') }}
                    </option>
                    <option value="es">
                      {{ t('settings.languages.es') }}
                    </option>
                  </select>
                </div>
              </div>

              <div class="flex flex-col gap-3 md:flex-row md:gap-7">
                <div class="md:w-44 md:flex-none">
                  <label class="block text-sm font-medium text-ink-2 mb-1">
                    {{ t('settings.timezone') }}
                  </label>
                  <p class="text-xs text-ink-3">
                    {{ t('settings.timezoneDesc') }}
                  </p>
                </div>
                <div class="min-w-0 md:max-w-[640px] md:flex-1">
                  <div class="rounded-lg border border-line bg-app-sub p-3">
                    <div class="text-sm font-medium text-ink">
                      {{ matchedTimezoneLabel }}
                    </div>
                    <div class="mt-1 text-xs text-ink-3">
                      {{ t('settings.detectedTimezone') }}:
                      {{ detectedTimezoneLabel }}
                    </div>
                  </div>
                </div>
              </div>

              <div class="flex flex-col gap-3 md:flex-row md:gap-7">
                <div class="md:w-44 md:flex-none">
                  <label class="block text-sm font-medium text-ink-2 mb-1">
                    {{ t('settings.scene') }}
                  </label>
                  <p class="text-xs text-ink-3">
                    {{ t('settings.sceneDesc') }}
                  </p>
                </div>
                <div class="min-w-0 md:max-w-[640px] md:flex-1">
                  <SceneSelector
                    v-model="preferenceForm.scene"
                    :label="''"
                    :error="''"
                  />
                </div>
              </div>

              <div class="bg-accent-soft border border-accent rounded-lg p-3">
                <p class="text-xs leading-relaxed text-accent">
                  {{ t('settings.preferenceChangeWarning') }}
                </p>
              </div>

              <div v-if="preferenceError" class="rounded-md bg-bad-soft p-3">
                <p class="text-sm text-bad">{{ preferenceError }}</p>
              </div>

              <div v-if="preferenceSuccess" class="rounded-md bg-ok-soft p-3">
                <p class="text-sm font-medium text-ok">
                  {{ preferenceSuccess }}
                </p>
              </div>

              <div class="flex justify-end">
                <BaseButton
                  type="button"
                  variant="primary"
                  class="w-full sm:w-auto"
                  :loading="savingPreferences"
                  :disabled="savingPreferences"
                  @click="savePreferences"
                >
                  {{
                    savingPreferences ? t('common.saving') : t('common.save')
                  }}
                </BaseButton>
              </div>
            </div>
          </div>

          <div v-else-if="activeSettingsTab === 'email'" class="space-y-6">
            <form class="space-y-5" @submit.prevent="saveEmailConfig">
              <MailboxSection :virtual-email="autoAssignedEmail" />

              <div
                class="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-start sm:justify-between"
                :class="
                  emailForm.processingPaused
                    ? 'border-warn bg-warn-soft'
                    : 'border-line bg-app-sub'
                "
              >
                <div>
                  <p class="text-sm font-medium text-ink">
                    {{ t('settings.pauseProcessing') }}
                  </p>
                  <p class="mt-1 max-w-xl text-xs leading-relaxed text-ink-2">
                    {{ t('settings.pauseProcessingHelp') }}
                  </p>
                </div>
                <label class="flex flex-shrink-0 items-center gap-2 text-sm">
                  <input
                    v-model="emailForm.processingPaused"
                    type="checkbox"
                    class="rounded border-line text-accent focus:ring-accent"
                  />
                  {{ t('settings.pauseProcessingLabel') }}
                </label>
              </div>

              <div class="bg-accent-soft border border-accent rounded-lg p-3">
                <p class="text-xs leading-relaxed text-accent">
                  {{ t('settings.emailConfigHint') }}
                </p>
              </div>

              <div v-if="emailError" class="rounded-md bg-bad-soft p-3">
                <p class="text-sm text-bad">{{ emailError }}</p>
              </div>

              <div v-if="emailSuccess" class="rounded-md bg-ok-soft p-3">
                <p class="text-sm font-medium text-ok">
                  {{ emailSuccess }}
                </p>
              </div>

              <div class="flex justify-end">
                <div class="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
                  <BaseButton
                    type="submit"
                    variant="primary"
                    class="w-full sm:w-auto"
                    :loading="savingEmailConfig"
                    :disabled="savingEmailConfig"
                  >
                    {{ saveEmailButtonLabel }}
                  </BaseButton>
                </div>
              </div>
            </form>
          </div>
        </div>

        <div
          v-if="showPasswordResetConfirm"
          class="fixed inset-0 bg-ink-2 bg-opacity-50 overflow-y-auto h-full w-full z-50"
          @click.self="showPasswordResetConfirm = false"
        >
          <div
            class="relative top-20 mx-auto p-6 border max-w-sm w-full shadow-lg rounded-md bg-panel"
          >
            <div class="mt-3">
              <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-medium text-ink">
                  {{ t('settings.confirmPasswordReset') }}
                </h3>
                <button
                  class="text-ink-4 hover:text-ink-2"
                  @click="showPasswordResetConfirm = false"
                >
                  <svg
                    class="w-6 h-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>

              <div class="mb-6">
                <div class="flex items-start gap-3">
                  <div class="flex-shrink-0">
                    <svg
                      class="h-6 w-6 text-accent"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                      />
                    </svg>
                  </div>
                  <div>
                    <p class="text-sm text-ink-2 mb-2">
                      {{ t('settings.passwordResetConfirmDesc') }}
                    </p>
                    <div class="bg-app-sub rounded-lg p-3">
                      <div class="text-sm font-medium text-ink mb-1">
                        {{ t('settings.securityEmail') }}
                      </div>
                      <div class="text-sm text-ink-2">
                        {{ userStore.userInfo?.email || '' }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="flex justify-end space-x-3">
                <BaseButton
                  variant="secondary"
                  @click="showPasswordResetConfirm = false"
                >
                  {{ t('common.cancel') }}
                </BaseButton>
                <BaseButton
                  variant="primary"
                  :loading="sendingResetEmail"
                  :disabled="sendingResetEmail"
                  @click="confirmPasswordReset"
                >
                  {{
                    sendingResetEmail
                      ? t('settings.sendingResetEmail')
                      : t('settings.sendPasswordReset')
                  }}
                </BaseButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { usePreferencesStore } from '@/store/preferences'
import { authApi } from '@/api/auth'
import { settingsApi } from '@/api/settings'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import SettingsNav from '@/components/settings/SettingsNav.vue'
import SettingsRow from '@/components/settings/SettingsRow.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import MailboxSection from '@/components/settings/MailboxSection.vue'
import SceneSelector from '@/components/ui/SceneSelector.vue'
import { getTimezoneLabel } from '@/utils/timezones'

const { t } = useI18n()
const userStore = useUserStore()
const preferencesStore = usePreferencesStore()

const activeSettingsTab = ref('account')
const loadingSettings = ref(true)
const savingPreferences = ref(false)
const savingEmailConfig = ref(false)
const errorMessage = ref('')
const preferenceError = ref('')
const preferenceSuccess = ref('')
const emailError = ref('')
const emailSuccess = ref('')

const sendingResetEmail = ref(false)
const resetEmailSent = ref(false)
const resetEmailError = ref('')
const showPasswordResetConfirm = ref(false)

const preferenceForm = reactive({
  language: 'en',
  timezone: 'UTC',
  scene: ''
})

// Filters live on the account rather than on each mailbox: someone who
// only wants invoices wants that from every mailbox they connect.
// Only the processing brake lives here now. Filters belong to the mailbox
// that uses them, and the virtual address arrives over SMTP, which never
// reads a filter config at all.
const emailForm = reactive({
  processingPaused: false
})

// Kept so saving the filters cannot drop settings this form does not show.
const rawEmailConfig = ref({})

const settingsTabs = computed(() => [
  {
    value: 'account',
    label: t('settings.basicInfo'),
    description: t('settings.basicInfoDesc')
  },
  {
    value: 'message',
    label: t('settings.preferences'),
    description: t('settings.preferencesDesc')
  },
  {
    value: 'email',
    label: t('settings.emailConfigTitle'),
    description: t('settings.emailConfigDesc')
  }
])

const activeSection = computed(
  () =>
    settingsTabs.value.find((tab) => tab.value === activeSettingsTab.value) ||
    settingsTabs.value[0]
)

const authInfo = computed(() => userStore.userInfo?.auth_info || null)
const isOauth = computed(() => authInfo.value?.method === 'oauth')

const displayedAiEmail = computed(
  () => userStore.userInfo?.virtual_email?.trim() || ''
)

const hasDisplayedAiEmail = computed(() => Boolean(displayedAiEmail.value))

const autoAssignedEmail = computed(() => {
  return userStore.userInfo?.virtual_email?.trim() || ''
})

const saveEmailButtonLabel = computed(() => {
  return savingEmailConfig.value ? t('common.saving') : t('common.save')
})

const displayName = computed(() => {
  const userInfo = userStore.userInfo
  if (!userInfo) return 'User'
  if (userInfo.display_name) return userInfo.display_name
  if (userInfo.first_name && userInfo.last_name) {
    return `${userInfo.first_name} ${userInfo.last_name}`
  }
  if (userInfo.first_name) return userInfo.first_name
  return userInfo.username || 'User'
})

const userInitials = computed(() => {
  const name = displayName.value || 'User'
  return name.trim().charAt(0).toUpperCase() || 'U'
})

const avatarBgColor = computed(() => {
  const colors = [
    'bg-accent',
    'bg-accent',
    'bg-accent',
    'bg-pink-500',
    'bg-bad',
    'bg-bad',
    'bg-warn',
    'bg-warn',
    'bg-warn',
    'bg-ok',
    'bg-ok',
    'bg-ok',
    'bg-accent',
    'bg-accent',
    'bg-accent'
  ]
  return colors[userInitials.value.charCodeAt(0) % colors.length]
})

const detectedTimezoneLabel = computed(() => {
  return getTimezoneLabel(preferencesStore.detectedTimezone || 'UTC')
})

const matchedTimezoneLabel = computed(() => {
  const timezone = preferenceForm.timezone || preferencesStore.detectedTimezone
  return getTimezoneLabel(timezone || 'UTC')
})

function goToEmailSettings() {
  activeSettingsTab.value = 'email'
}

function normalizeUiLanguageCode(language) {
  if (!language || typeof language !== 'string') {
    return 'en'
  }

  const value = language.trim().toLowerCase()
  if (value.startsWith('zh')) {
    return 'zh-CN'
  }
  if (value.startsWith('es')) {
    return 'es'
  }
  return 'en'
}

function normalizeEmailConfig(value) {
  const raw = value && typeof value === 'object' ? value : {}
  rawEmailConfig.value = raw
  emailForm.processingPaused = Boolean(raw.processing_paused)
}
function buildEmailConfig() {
  // This form owns the brake and nothing else; anything already stored is
  // carried through untouched rather than rewritten from a screen that no
  // longer shows it.
  return {
    ...(rawEmailConfig.value || {}),
    processing_paused: Boolean(emailForm.processingPaused)
  }
}

function extractErrorMessage(error, fallback) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.error ||
    error?.response?.data?.detail ||
    error?.response?.data?.data?.error ||
    fallback
  )
}

async function loadSettings() {
  loadingSettings.value = true
  errorMessage.value = ''

  try {
    if (!userStore.userInfo || !userStore.userInfo.virtual_email) {
      await userStore.checkAuthStatus()
    }

    const settingsList = await settingsApi.getSettingsList()
    const settingsByKey = Object.fromEntries(
      settingsList.map((setting) => [setting.key, setting])
    )

    const profile = userStore.userInfo?.profile || {}
    const promptConfig = settingsByKey.prompt_config?.value || {}

    preferenceForm.language = normalizeUiLanguageCode(
      promptConfig.language || profile.language || 'en'
    )
    preferenceForm.timezone =
      profile.timezone ||
      preferencesStore.currentTimezone ||
      preferencesStore.detectedTimezone ||
      'UTC'
    preferenceForm.scene = promptConfig.scene || ''

    normalizeEmailConfig(settingsByKey.email_config?.value)
  } catch (error) {
    console.error('Failed to load settings:', error)
    errorMessage.value = extractErrorMessage(error, t('settings.settingsError'))
  } finally {
    loadingSettings.value = false
  }
}

function clearSectionFeedback(section) {
  if (section === 'preference') {
    preferenceError.value = ''
    preferenceSuccess.value = ''
  } else if (section === 'email') {
    emailError.value = ''
    emailSuccess.value = ''
  }
}

function setSectionSuccess(section, message) {
  if (section === 'preference') {
    preferenceSuccess.value = message
    setTimeout(() => {
      if (preferenceSuccess.value === message) {
        preferenceSuccess.value = ''
      }
    }, 3000)
  } else if (section === 'email') {
    emailSuccess.value = message
    setTimeout(() => {
      if (emailSuccess.value === message) {
        emailSuccess.value = ''
      }
    }, 3000)
  }
}

function setSectionError(section, message) {
  if (section === 'preference') {
    preferenceError.value = message
  } else if (section === 'email') {
    emailError.value = message
  }
}

async function savePreferences() {
  savingPreferences.value = true
  clearSectionFeedback('preference')

  try {
    await userStore.updateProfile({
      language: preferenceForm.language,
      timezone: preferenceForm.timezone
    })

    await settingsApi.saveSettingByKey({
      key: 'prompt_config',
      value: {
        language: preferenceForm.language,
        scene: preferenceForm.scene
      },
      description: 'User prompt configuration (language and scene)'
    })

    preferencesStore.setTimezone(preferenceForm.timezone)
    preferencesStore.loadFromBackend({
      language: preferenceForm.language,
      scene: preferenceForm.scene
    })

    setSectionSuccess('preference', t('settings.settingsSaved'))
  } catch (error) {
    console.error('Failed to save preferences:', error)
    setSectionError(
      'preference',
      extractErrorMessage(error, t('settings.settingsError'))
    )
  } finally {
    savingPreferences.value = false
  }
}

async function saveEmailConfig() {
  savingEmailConfig.value = true
  clearSectionFeedback('email')

  try {
    const nextEmailConfig = buildEmailConfig()

    await settingsApi.saveSettingByKey({
      key: 'email_config',
      value: nextEmailConfig,
      description: 'User email configuration'
    })

    setSectionSuccess('email', t('settings.settingsSaved'))
  } catch (error) {
    console.error('Failed to save email config:', error)
    setSectionError(
      'email',
      extractErrorMessage(error, t('settings.settingsError'))
    )
  } finally {
    savingEmailConfig.value = false
  }
}

async function confirmPasswordReset() {
  sendingResetEmail.value = true
  resetEmailError.value = ''
  resetEmailSent.value = false

  try {
    await authApi.resetPassword(userStore.userInfo?.email)
    resetEmailSent.value = true
    showPasswordResetConfirm.value = false

    setTimeout(() => {
      resetEmailSent.value = false
    }, 5000)
  } catch (error) {
    console.error('Password reset email failed:', error)
    resetEmailError.value = extractErrorMessage(
      error,
      t('settings.passwordResetError')
    )
  } finally {
    sendingResetEmail.value = false
  }
}

onMounted(async () => {
  await loadSettings()
})
</script>
