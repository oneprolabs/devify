<template>
  <AppLayout>
    <div class="max-w-5xl mx-auto space-y-6">
      <div class="space-y-1">
        <h2 class="text-xl font-bold leading-7 text-ink sm:text-2xl">
          {{ t('settings.title') }}
        </h2>
        <p class="text-sm text-ink-3">
          {{ t('settings.subtitle') }}
        </p>
      </div>

      <div
        v-if="loadingSettings"
        class="rounded-md bg-app-sub border border-line p-4 text-sm text-ink-2"
      >
        {{ t('settings.loadingSettings') }}
      </div>

      <div class="border-b border-line">
        <div
          class="flex gap-6 overflow-x-auto whitespace-nowrap [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          role="tablist"
          aria-label="Settings categories"
        >
          <button
            v-for="tab in settingsTabs"
            :key="tab.value"
            type="button"
            class="flex-shrink-0 border-b-2 px-1 py-3 text-xs font-medium transition-colors sm:text-sm"
            role="tab"
            :aria-selected="activeSettingsTab === tab.value"
            :class="
              activeSettingsTab === tab.value
                ? 'border-accent text-accent'
                : 'border-transparent text-ink-3 hover:border-line hover:text-ink-2'
            "
            @click="activeSettingsTab = tab.value"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>

      <div v-if="activeSettingsTab === 'account'" class="space-y-6">
        <div class="bg-panel rounded-lg border border-line p-4 sm:p-5">
          <div class="flex items-center gap-3">
            <div
              :class="avatarBgColor"
              class="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0"
            >
              <span class="text-accent-on font-medium text-lg">
                {{ userInitials }}
              </span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-lg font-semibold text-ink truncate">
                {{ displayName }}
              </div>
              <div class="text-sm text-ink-3 truncate">
                {{ userStore.userInfo?.email || '' }}
              </div>
            </div>
          </div>
        </div>

        <BaseCard :header-muted="true">
          <template #header>
            <div class="flex items-center gap-2 text-ink">
              <svg
                class="w-5 h-5 -mt-px flex-none"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
              <h3 class="text-base font-semibold leading-5">
                {{ t('settings.basicInfo') }}
              </h3>
            </div>
          </template>

          <div class="space-y-4">
            <div>
              <h4 class="text-sm font-medium text-ink mb-2">
                {{ t('settings.aiEmail') }}
              </h4>
              <div
                v-if="loadingSettings"
                class="rounded-lg border border-line bg-app-sub p-3 animate-pulse"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1 space-y-3">
                    <div class="h-3 w-20 rounded bg-chip"></div>
                    <div class="h-4 w-56 max-w-full rounded bg-chip"></div>
                    <div class="h-3 w-72 max-w-full rounded bg-chip"></div>
                  </div>
                  <div class="h-8 w-24 rounded-md bg-chip"></div>
                </div>
              </div>
              <div
                v-else-if="hasDisplayedAiEmail"
                class="rounded-lg border p-3 transition-colors"
                :class="'border-accent bg-accent-soft'"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div
                      class="text-xs font-medium tracking-wide"
                      :class="'text-accent'"
                    >
                      {{ t('settings.aiEmail') }}
                    </div>
                    <div
                      class="mt-1 text-sm font-mono truncate"
                      :class="'text-accent'"
                    >
                      {{ displayedAiEmail }}
                    </div>
                    <div class="mt-2 text-xs leading-5" :class="'text-accent'">
                      {{ t('settings.aiEmailDesc') }}
                    </div>
                  </div>
                  <button
                    type="button"
                    class="flex-shrink-0 inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-md transition-colors"
                    :class="'text-accent hover:text-accent bg-accent-soft hover:bg-accent'"
                    @click="goToEmailSettings"
                  >
                    {{ t('settings.goToEmailSettings') }}
                  </button>
                </div>
              </div>
              <div
                v-else
                class="rounded-lg border border-warn bg-warn-soft p-3"
              >
                <div class="flex items-start gap-2">
                  <svg
                    class="mt-0.5 h-4 w-4 flex-none text-warn"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M12 9v2m0 4h.01M10.29 3.86l-7.2 12.48A1.5 1.5 0 004.39 18h15.22a1.5 1.5 0 001.3-2.24l-7.2-12.48a1.5 1.5 0 00-2.62 0z"
                    />
                  </svg>
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-warn">
                      {{ t('settings.noAiEmailConfigured') }}
                    </p>
                    <p class="mt-1 text-xs leading-5 text-warn">
                      {{ t('settings.noAiEmailHint') }}
                    </p>
                    <button
                      type="button"
                      class="mt-2 inline-flex items-center text-xs font-medium text-warn hover:text-warn"
                      @click="goToEmailSettings"
                    >
                      {{ t('settings.goToEmailSettings') }}
                      <svg
                        class="ml-1 h-3.5 w-3.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <h4 class="text-sm font-medium text-ink mb-2">
                {{ t('settings.authMethod') }}
              </h4>
              <p class="text-sm text-ink-2">
                <span
                  v-if="authInfo && authInfo.method === 'email'"
                  class="inline-flex items-center"
                >
                  <svg
                    class="h-4 w-4 mr-1.5 text-accent"
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
                  {{ t('settings.emailAuth') }}
                </span>
                <span
                  v-else-if="authInfo && authInfo.method === 'oauth'"
                  class="inline-flex items-center"
                >
                  <svg
                    class="h-4 w-4 mr-1.5 text-ok"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                    />
                  </svg>
                  {{ t('settings.oauthAuth') }}
                </span>
                <span v-else class="inline-flex items-center">
                  {{ t('settings.emailAuth') }}
                </span>
              </p>
            </div>

            <div v-if="authInfo && authInfo.method === 'oauth'">
              <div class="bg-ok-soft rounded-lg p-3">
                <div class="flex items-center gap-2 mb-1">
                  <svg
                    class="w-4 h-4 text-ok"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                    />
                  </svg>
                  <span class="text-xs font-medium text-ok">
                    {{ authInfo.provider || 'OAuth' }}
                  </span>
                </div>
                <div class="text-sm text-ok">
                  {{ authInfo.login_identifier || '' }}
                </div>
              </div>
            </div>

            <div
              v-if="authInfo?.method === 'oauth' && authInfo?.provider_email"
              class="bg-app-sub rounded-lg p-3"
            >
              <div class="text-xs text-ink-3 space-y-1">
                <p>
                  <span class="font-medium"
                    >{{ t('settings.oauthProvider') }}:</span
                  >
                  {{ authInfo.provider }}
                </p>
                <p>
                  <span class="font-medium"
                    >{{ t('settings.oauthEmail') }}:</span
                  >
                  {{ authInfo.provider_email }}
                </p>
              </div>
            </div>

            <div v-if="authInfo?.can_change_password" class="flex justify-end">
              <BaseButton
                variant="primary"
                class="w-full sm:w-auto"
                @click="showPasswordResetConfirm = true"
              >
                {{ t('settings.resetPassword') }}
              </BaseButton>
            </div>

            <div
              v-if="!authInfo?.can_change_password"
              class="bg-warn-soft border border-warn rounded-lg p-3"
            >
              <div class="flex gap-2">
                <div class="flex-shrink-0 pt-0.5">
                  <svg
                    class="h-5 w-5 text-warn"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clip-rule="evenodd"
                    />
                  </svg>
                </div>
                <div class="ml-1">
                  <p class="text-sm text-warn">
                    {{ t('settings.oauthPasswordChangeInfo') }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </BaseCard>

        <div v-if="resetEmailSent || resetEmailError" class="space-y-4">
          <div v-if="resetEmailSent" class="rounded-md bg-ok-soft p-4">
            <div class="flex">
              <div class="flex-shrink-0">
                <svg
                  class="h-5 w-5 text-ok"
                  viewBox="0 0 20 20"
                  fill="currentColor"
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
                  {{ t('settings.passwordResetEmailSent') }}
                </p>
                <p class="text-xs text-ok mt-1">
                  {{ t('settings.passwordResetEmailSentDesc') }}
                </p>
              </div>
            </div>
          </div>

          <div v-if="resetEmailError" class="rounded-md bg-bad-soft p-4">
            <div class="flex">
              <div class="flex-shrink-0">
                <svg
                  class="h-5 w-5 text-bad"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clip-rule="evenodd"
                  />
                </svg>
              </div>
              <div class="ml-3">
                <p class="text-sm font-medium text-bad">
                  {{ resetEmailError }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="activeSettingsTab === 'message'" class="space-y-6">
        <BaseCard :header-muted="true">
          <template #header>
            <div class="flex items-center gap-2 text-ink">
              <svg
                class="w-5 h-5 -mt-px flex-none"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
              <h3 class="text-base font-semibold leading-5">
                {{ t('settings.preferences') }}
              </h3>
            </div>
          </template>

          <div class="space-y-5">
            <div
              class="grid grid-cols-1 gap-2 md:grid-cols-3 md:gap-4 md:items-start"
            >
              <div class="md:col-span-1">
                <label class="block text-sm font-medium text-ink-2 mb-1">
                  {{ t('settings.language') }}
                </label>
                <p class="text-xs text-ink-3">
                  {{ t('settings.languageDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
                <select
                  v-model="preferenceForm.language"
                  class="block w-full pl-3 pr-10 py-2 text-sm border-line bg-panel focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent rounded-md shadow-sm appearance-none cursor-pointer hover:border-line transition-colors"
                >
                  <option value="en">{{ t('settings.languages.en') }}</option>
                  <option value="zh-CN">
                    {{ t('settings.languages.zh-CN') }}
                  </option>
                  <option value="es">{{ t('settings.languages.es') }}</option>
                </select>
              </div>
            </div>

            <div
              class="grid grid-cols-1 gap-2 md:grid-cols-3 md:gap-4 md:items-start"
            >
              <div class="md:col-span-1">
                <label class="block text-sm font-medium text-ink-2 mb-1">
                  {{ t('settings.timezone') }}
                </label>
                <p class="text-xs text-ink-3">
                  {{ t('settings.timezoneDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
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

            <div
              class="grid grid-cols-1 gap-2 md:grid-cols-3 md:gap-4 md:items-start"
            >
              <div class="md:col-span-1">
                <label class="block text-sm font-medium text-ink-2 mb-1">
                  {{ t('settings.scene') }}
                </label>
                <p class="text-xs text-ink-3">
                  {{ t('settings.sceneDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
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
                {{ savingPreferences ? t('common.saving') : t('common.save') }}
              </BaseButton>
            </div>
          </div>
        </BaseCard>
      </div>

      <div v-else-if="activeSettingsTab === 'email'" class="space-y-6">
        <BaseCard :header-muted="true">
          <template #header>
            <div class="flex items-center gap-2 text-ink">
              <svg
                class="w-5 h-5 -mt-px flex-none"
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
              <h3 class="text-base font-semibold leading-5">
                {{ t('settings.emailConfigTitle') }}
              </h3>
            </div>
          </template>

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
        </BaseCard>
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
import BaseCard from '@/components/ui/BaseCard.vue'
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
    label: t('settings.basicInfo')
  },
  {
    value: 'message',
    label: t('settings.preferences')
  },
  {
    value: 'email',
    label: t('settings.emailConfigTitle')
  }
])

const authInfo = computed(() => userStore.userInfo?.auth_info || null)

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
