<template>
  <div class="min-h-screen lg:flex">
    <!-- What the product does, for someone deciding whether to sign up.
         It carries no controls, so the narrow layout drops this column and
         restates the three steps in one line above the form instead. -->
    <aside
      class="hidden border-r border-line bg-app-sub px-14 py-12 lg:flex lg:w-[41.4%] lg:flex-col lg:justify-between"
    >
      <div class="flex items-center gap-2.5">
        <img
          src="/android-chrome-192x192.png"
          alt=""
          class="h-[30px] w-[30px] rounded-lg"
        />
        <span class="text-lg font-semibold text-ink">AImyChats</span>
      </div>

      <div class="flex flex-col gap-[30px]">
        <h2
          class="whitespace-pre-line text-[27px] font-semibold leading-snug text-ink"
        >
          {{ t('auth.pitch.headline') }}
        </h2>

        <ol class="flex flex-col">
          <li
            v-for="(step, index) in pitchSteps"
            :key="step.key"
            class="flex gap-[15px]"
          >
            <div class="flex flex-col items-center">
              <span
                class="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-full bg-accent-soft text-accent"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.9"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                >
                  <path :d="step.icon" />
                </svg>
              </span>
              <span
                v-if="index < pitchSteps.length - 1"
                class="w-px flex-1 bg-line"
              ></span>
            </div>
            <div class="flex flex-col gap-1 pb-[22px]">
              <span class="text-sm font-semibold text-ink">
                {{ t(`auth.pitch.${step.key}.title`) }}
              </span>
              <span
                v-if="step.body"
                class="text-[12.5px] leading-relaxed text-ink-3"
              >
                {{ t(`auth.pitch.${step.key}.body`) }}
              </span>
              <div v-if="step.targets" class="mt-1 flex flex-wrap gap-1.5">
                <span
                  v-for="target in deliveryTargets"
                  :key="target"
                  class="rounded bg-chip px-2.5 py-1 text-[11px] text-ink-2"
                >
                  {{ t(target) }}
                </span>
              </div>
            </div>
          </li>
        </ol>
      </div>

      <p class="text-[11px] text-ink-4">© 2026 AImyChats</p>
    </aside>

    <div
      class="flex min-h-screen flex-1 items-start justify-center bg-app px-4 py-8 sm:px-6 lg:items-center lg:py-12"
    >
      <div class="w-full max-w-[376px] space-y-[22px]">
        <!-- The narrow layout has no left panel, so the pitch comes back
             here as a headline and one line naming the three steps. -->
        <div class="flex flex-col gap-[18px] lg:hidden">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <img
                src="/android-chrome-192x192.png"
                alt=""
                class="h-[30px] w-[30px] rounded-lg"
              />
              <span class="text-lg font-semibold text-ink">AImyChats</span>
            </div>
            <LanguageSwitcher />
          </div>
          <div class="flex flex-col gap-2">
            <h2
              class="whitespace-pre-line text-[22px] font-semibold leading-snug text-ink"
            >
              {{ t('auth.pitch.headline') }}
            </h2>
            <p class="text-[12.5px] leading-relaxed text-ink-3">
              {{ t('auth.pitch.summary') }}
            </p>
          </div>
        </div>

        <!-- Tab Navigation -->
        <div class="flex items-center justify-between">
          <div class="flex gap-[22px]">
            <button
              v-for="tab in ['login', 'register']"
              :key="tab"
              type="button"
              class="border-b-2 pb-[9px] text-base transition-colors"
              :class="
                activeTab === tab
                  ? 'border-accent font-semibold text-accent'
                  : 'border-transparent font-medium text-ink-3 hover:text-ink-2'
              "
              @click="activeTab = tab"
            >
              {{ t(`auth.tabs.${tab}`) }}
            </button>
          </div>
          <LanguageSwitcher class="hidden lg:block" />
        </div>

        <!-- Success message (email sent) -->
        <div
          v-if="emailSent"
          class="rounded-md bg-ok-soft border border-ok p-4"
        >
          <div class="flex">
            <div class="flex-shrink-0">
              <svg
                class="h-5 w-5 text-ok"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fill-rule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clip-rule="evenodd"
                />
              </svg>
            </div>
            <div class="ml-3">
              <h3 class="text-sm font-medium text-ok">
                {{ t('register.emailSent.title') }}
              </h3>
              <div class="mt-2 text-sm text-ok">
                <p>
                  {{
                    t('register.emailSent.message', { email: formData.email })
                  }}
                </p>
              </div>
            </div>
          </div>
          <div class="mt-4">
            <BaseButton block variant="primary" @click="handleReturnToLogin">
              {{ t('register.emailSent.backToLogin') }}
            </BaseButton>
          </div>
        </div>

        <!-- Google OAuth Button (Priority) -->
        <div v-if="!emailSent">
          <a
            :href="googleOAuthUrl"
            class="w-full flex items-center justify-center px-4 py-3 border border-line rounded-lg shadow-sm bg-panel text-sm font-medium text-ink-2 hover:bg-app-sub transition-colors"
          >
            <svg class="w-5 h-5 mr-2" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            {{ t('auth.oauth.continueWithGoogle') }}
          </a>

          <!-- Divider -->
          <div class="relative mt-6">
            <div class="absolute inset-0 flex items-center">
              <div class="w-full border-t border-line" />
            </div>
            <div class="relative flex justify-center text-sm">
              <span class="px-2 bg-app text-ink-3">
                {{ t('auth.divider.or') }}
              </span>
            </div>
          </div>
        </div>

        <!-- Login Form -->
        <form
          v-if="activeTab === 'login' && !emailSent"
          class="mt-6 space-y-4"
          @submit.prevent="handleLogin"
        >
          <div>
            <label class="block text-sm font-medium text-ink-2 mb-1">
              {{ t('auth.virtualEmailUsername') }}
            </label>
            <div class="flex rounded-md shadow-sm">
              <input
                v-model="formData.username"
                type="text"
                name="username"
                autocomplete="username"
                :placeholder="t('auth.username')"
                required
                :disabled="loading"
                class="input rounded-r-none flex-1"
                :class="{ 'input-error': errors.username }"
              />
              <span
                class="inline-flex items-center px-3 rounded-r-md border border-l-0 border-line bg-app-sub text-ink-3 text-sm"
              >
                @{{ emailDomain }}
              </span>
            </div>
            <p v-if="errors.username" class="mt-1 text-sm text-bad">
              {{ errors.username }}
            </p>
          </div>

          <BaseInput
            v-model="formData.password"
            :label="t('auth.password')"
            type="password"
            name="password"
            autocomplete="current-password"
            :placeholder="t('auth.password')"
            required
            :error="errors.password"
            :disabled="loading"
          />

          <div class="flex items-center justify-end">
            <div class="text-sm">
              <a
                href="#"
                @click.prevent="showForgotPassword = true"
                class="font-medium text-accent hover:text-accent"
              >
                {{ t('auth.forgotPassword') }}
              </a>
            </div>
          </div>

          <div
            v-if="errorMessage"
            class="rounded-md bg-bad-soft border border-bad p-4"
          >
            <p class="text-sm text-bad">
              {{ errorMessage }}
            </p>
          </div>

          <BaseButton
            type="submit"
            variant="primary"
            class="w-full"
            :loading="loading"
            :disabled="loading"
          >
            {{ loading ? t('auth.signingIn') : t('auth.signIn') }}
          </BaseButton>
        </form>

        <!-- Register Form -->
        <form
          v-if="activeTab === 'register' && !emailSent"
          class="mt-6 space-y-4"
          @submit.prevent="handleRegister"
        >
          <BaseInput
            v-model="formData.email"
            :label="t('auth.email')"
            type="email"
            name="email"
            autocomplete="email"
            :placeholder="t('register.emailPlaceholder')"
            required
            :error="errors.email"
            :disabled="loading"
          />

          <p class="text-sm text-ink-3">
            {{ t('register.emailHint') }}
          </p>

          <div
            v-if="errorMessage"
            class="rounded-md bg-bad-soft border border-bad p-4"
          >
            <p class="text-sm text-bad">
              {{ errorMessage }}
            </p>
          </div>

          <BaseButton
            type="submit"
            variant="primary"
            class="w-full"
            :loading="loading"
            :disabled="loading || !formData.email"
          >
            {{ loading ? t('register.sending') : t('register.sendEmail') }}
          </BaseButton>
        </form>

        <p v-if="!emailSent" class="text-center text-[12.5px] text-ink-3">
          {{
            activeTab === 'login'
              ? t('auth.noAccountYet')
              : t('auth.haveAccount')
          }}
          <button
            type="button"
            class="font-medium text-accent hover:underline"
            @click="activeTab = activeTab === 'login' ? 'register' : 'login'"
          >
            {{
              activeTab === 'login'
                ? t('auth.tabs.register')
                : t('auth.tabs.login')
            }}
          </button>
        </p>
      </div>
    </div>

    <!-- Forgot Password Modal, outside the two columns so it covers both -->
    <div
      v-if="showForgotPassword"
      class="fixed inset-0 z-50 overflow-y-auto"
      aria-labelledby="modal-title"
      role="dialog"
      aria-modal="true"
    >
      <div
        class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0"
      >
        <!-- Background overlay -->
        <div
          class="fixed inset-0 bg-ink-3 bg-opacity-75 transition-opacity"
          aria-hidden="true"
          @click="closeForgotPassword"
        ></div>

        <!-- Center modal -->
        <span
          class="hidden sm:inline-block sm:align-middle sm:h-screen"
          aria-hidden="true"
          >&#8203;</span
        >

        <!-- Modal content -->
        <div
          class="inline-block align-bottom bg-panel rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6"
        >
          <div>
            <div class="mt-3 text-center sm:mt-5">
              <h3
                class="text-lg leading-6 font-medium text-ink"
                id="modal-title"
              >
                {{ t('auth.forgotPassword') }}
              </h3>
              <div class="mt-2">
                <p class="text-sm text-ink-3">
                  {{ t('auth.forgotPasswordDescription') }}
                </p>
              </div>
            </div>
          </div>

          <!-- Success message -->
          <div
            v-if="resetEmailSent"
            class="mt-4 rounded-md bg-ok-soft border border-ok p-4"
          >
            <div class="flex">
              <div class="flex-shrink-0">
                <svg
                  class="h-5 w-5 text-ok"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clip-rule="evenodd"
                  />
                </svg>
              </div>
              <div class="ml-3">
                <p class="text-sm font-medium text-ok">
                  {{ t('auth.resetEmailSent') }}
                </p>
              </div>
            </div>
          </div>

          <!-- Error message -->
          <div
            v-else-if="resetErrorMessage"
            class="mt-4 rounded-md bg-bad-soft border border-bad p-4"
          >
            <div class="flex">
              <div class="flex-shrink-0">
                <svg
                  class="h-5 w-5 text-bad"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clip-rule="evenodd"
                  />
                </svg>
              </div>
              <div class="ml-3">
                <p class="text-sm text-bad">
                  {{ resetErrorMessage }}
                </p>
              </div>
            </div>
          </div>

          <!-- Email input form -->
          <form
            v-if="!resetEmailSent"
            @submit.prevent="handleForgotPassword"
            class="mt-5"
          >
            <div>
              <label
                for="reset-email"
                class="block text-sm font-medium text-ink-2"
              >
                {{ t('settings.securityEmail') }}
              </label>
              <div class="mt-1">
                <input
                  id="reset-email"
                  v-model="resetEmail"
                  type="email"
                  required
                  class="appearance-none block w-full px-3 py-2 border border-line rounded-md shadow-sm placeholder-line focus:outline-none focus:ring-accent focus:border-accent sm:text-sm"
                  :placeholder="
                    t('auth.securityEmailPlaceholder') ||
                    t('auth.emailPlaceholder')
                  "
                  :disabled="resetLoading"
                />
              </div>
            </div>

            <div
              class="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense"
            >
              <button
                type="submit"
                :disabled="resetLoading || !resetEmail"
                class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-accent text-base font-medium text-accent-on hover:bg-accent focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent sm:col-start-2 sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ resetLoading ? t('common.loading') : t('common.submit') }}
              </button>
              <button
                type="button"
                @click="closeForgotPassword"
                class="mt-3 w-full inline-flex justify-center rounded-md border border-line shadow-sm px-4 py-2 bg-panel text-base font-medium text-ink-2 hover:bg-app-sub focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent sm:mt-0 sm:col-start-1 sm:text-sm"
              >
                {{ t('common.cancel') }}
              </button>
            </div>
          </form>

          <!-- Close button when email sent -->
          <div v-else class="mt-5">
            <button
              type="button"
              @click="closeForgotPassword"
              class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-accent text-base font-medium text-accent-on hover:bg-accent focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent sm:text-sm"
            >
              {{ t('common.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { sendRegistrationEmail, resetPassword } from '@/api/auth'
import apiConfig from '@/config/api'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import LanguageSwitcher from '@/components/ui/LanguageSwitcher.vue'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// What the left panel promises, in the order the flow actually happens.
const pitchSteps = [
  {
    key: 'forward',
    icon: 'M4 6h16v12H4z M4 7l8 6 8-6',
    body: true
  },
  {
    key: 'organise',
    icon: 'M4 7h16M4 12h16M4 17h10',
    body: true
  },
  {
    // The channel chips say what this step delivers to, so it needs no prose.
    key: 'deliver',
    icon: 'M4 12h12m0 0-4-4m4 4-4 4M18 5v14',
    targets: true
  }
]

// The same three channels Relay names, so the promise matches the product.
const deliveryTargets = [
  'relay.targetFeishu',
  'relay.targetJira',
  'relay.targetGitHub'
]

const activeTab = ref(route.query.tab === 'register' ? 'register' : 'login')

// Get email domain from environment variable
const emailDomain = import.meta.env.VITE_EMAIL_DOMAIN || 'devify.local'

const formData = reactive({
  username: '',
  password: '',
  email: ''
})

const errors = reactive({
  username: '',
  password: '',
  email: ''
})

const loading = ref(false)
const errorMessage = ref('')
const emailSent = ref(false)

const showForgotPassword = ref(false)
const resetEmail = ref('')
const resetLoading = ref(false)
const resetErrorMessage = ref('')
const resetEmailSent = ref(false)

const googleOAuthUrl = computed(() => {
  // Use centralized API configuration
  // Returns the configured Google OAuth login endpoint
  return apiConfig.endpoints.googleLogin()
})

watch(activeTab, (newTab) => {
  errorMessage.value = ''
  errors.username = ''
  errors.password = ''
  errors.email = ''

  router.replace({ query: { tab: newTab } })
})

const validateLogin = () => {
  errors.username = ''
  errors.password = ''

  if (!formData.username.trim()) {
    errors.username = t('auth.required.username')
    return false
  }

  if (!formData.password) {
    errors.password = t('auth.required.password')
    return false
  }

  return true
}

const validateEmail = () => {
  errors.email = ''

  if (!formData.email) {
    errors.email = t('auth.required.email')
    return false
  }

  if (!/\S+@\S+\.\S+/.test(formData.email)) {
    errors.email = t('auth.invalid.email')
    return false
  }

  return true
}

const handleLogin = async () => {
  if (!validateLogin()) {
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    await userStore.login({
      username: formData.username,
      password: formData.password
    })

    router.push('/chats')
  } catch (error) {
    console.error('Login error:', error)
    errorMessage.value = t('auth.loginError')
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  if (!validateEmail()) {
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const response = await sendRegistrationEmail({
      email: formData.email,
      language: locale.value || 'en-US'
    })

    const responseData = response.data.data || response.data

    if (responseData.success || response.data.code === 0) {
      emailSent.value = true
    }
  } catch (error) {
    console.error('Send email error:', error)

    const errorData = error.response?.data?.data || error.response?.data

    if (errorData?.errors?.email) {
      errors.email = errorData.errors.email[0]
    } else if (errorData?.error) {
      errorMessage.value = errorData.error
    } else {
      errorMessage.value = t('register.sendEmailError')
    }
  } finally {
    loading.value = false
  }
}

const handleForgotPassword = async () => {
  resetErrorMessage.value = ''
  resetLoading.value = true

  try {
    const response = await resetPassword(resetEmail.value)
    const responseData = response.data?.data || response.data

    if (responseData.success || response.data.code === 0) {
      resetEmailSent.value = true
    }
  } catch (error) {
    console.error('Reset password error:', error)

    const errorData = error.response?.data?.data || error.response?.data

    if (errorData?.error) {
      resetErrorMessage.value = errorData.error
    } else if (errorData?.errors?.email) {
      resetErrorMessage.value = errorData.errors.email[0]
    } else {
      resetErrorMessage.value = t('auth.resetPasswordError')
    }
  } finally {
    resetLoading.value = false
  }
}

const handleReturnToLogin = () => {
  emailSent.value = false
  activeTab.value = 'login'
}

const closeForgotPassword = () => {
  showForgotPassword.value = false
  resetEmail.value = ''
  resetLoading.value = false
  resetErrorMessage.value = ''
  resetEmailSent.value = false
}
</script>
