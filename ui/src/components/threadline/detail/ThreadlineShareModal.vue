<template>
  <BaseModal
    :show="showShareModal"
    :title="t('share.modalTitle')"
    @close="closeShareModal"
  >
    <div class="space-y-4 text-sm text-ink-2">
      <p class="text-ink-2">
        {{ t('share.modalDescription') }}
      </p>

      <div
        v-if="shareStatus?.is_active"
        class="rounded-md border border-line bg-app-sub p-3 space-y-2"
      >
        <div class="text-xs font-medium text-ink-3">
          {{ t('share.currentShare') }}
        </div>
        <div class="flex items-center gap-2 min-w-0">
          <a
            v-if="!showShareLink.modal"
            :href="shareStatus.share_url"
            target="_blank"
            class="text-sm text-ink-2 hover:text-accent transition-colors"
          >
            <span>{{ t('share.openLink') }}</span>
          </a>
          <a
            v-else
            :href="shareStatus.share_url"
            target="_blank"
            class="text-sm text-ink-2 truncate font-mono hover:text-accent hover:underline flex-1 min-w-0"
          >
            {{ shareStatus.share_url }}
          </a>
          <button
            type="button"
            class="p-1 text-ink-4 hover:text-ink-2 rounded hover:bg-chip transition-colors flex-shrink-0"
            :title="
              showShareLink.modal ? t('share.hideLink') : t('share.openLink')
            "
            @click="showShareLink.modal = !showShareLink.modal"
          >
            <svg
              v-if="!showShareLink.modal"
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
              />
            </svg>
            <svg
              v-else
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
              />
            </svg>
          </button>
          <button
            type="button"
            class="p-1 text-ink-4 hover:text-ink-2 rounded hover:bg-chip transition-colors flex-shrink-0"
            :title="shareCopyState.link ? t('share.copied') : t('share.copy')"
            @click="copyShareLink"
          >
            <svg
              v-if="!shareCopyState.link"
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
            <svg
              v-else
              class="w-4 h-4 text-ok"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M5 13l4 4L19 7"
              />
            </svg>
          </button>
        </div>
      </div>

      <div class="space-y-2">
        <span class="text-xs font-medium text-ink-2">{{
          t('share.expirationLabel')
        }}</span>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="option in shareExpirationOptions"
            :key="option.value"
            type="button"
            class="rounded-md border px-3 py-1.5 text-xs font-medium transition-colors"
            :class="
              shareForm.expiration === option.value
                ? 'border-accent bg-accent-soft text-accent'
                : 'border-line text-ink-2'
            "
            @click="shareForm.expiration = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <div class="space-y-2">
        <label class="flex items-center gap-2 text-xs font-medium text-ink-2">
          <input
            type="checkbox"
            v-model="shareForm.requirePassword"
            class="rounded border-line text-accent focus:ring-accent"
          />
          {{ t('share.passwordToggleLabel') }}
        </label>
        <p class="text-xs text-ink-3">
          {{ t('share.passwordHint') }}
        </p>
        <div v-if="shareForm.requirePassword" class="flex items-stretch gap-2">
          <input
            v-model="shareForm.password"
            inputmode="numeric"
            maxlength="6"
            minlength="6"
            pattern="[0-9]*"
            class="flex-1 rounded-md border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
            :placeholder="t('share.passwordPlaceholder')"
          />
          <BaseButton
            variant="secondary"
            size="sm"
            @click="generateLocalPassword"
          >
            {{ t('share.generatePassword') }}
          </BaseButton>
        </div>
      </div>

      <div
        v-if="sharePasswordDisplay"
        class="rounded-md border border-ok bg-ok-soft p-3 space-y-2"
      >
        <div class="text-xs font-medium text-ok">
          {{ t('share.generatedPasswordLabel') }}
        </div>
        <div class="flex items-center justify-between">
          <span class="text-lg font-mono text-ink">
            {{ sharePasswordDisplay }}
          </span>
          <button
            class="p-1 text-ink-4 hover:text-ink-2 rounded hover:bg-chip transition-colors flex-shrink-0"
            :title="
              shareCopyState.password ? t('share.copied') : t('share.copy')
            "
            type="button"
            @click="copySharePassword"
          >
            <svg
              v-if="!shareCopyState.password"
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
            <svg
              v-else
              class="w-4 h-4 text-ok"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M5 13l4 4L19 7"
              />
            </svg>
          </button>
        </div>
      </div>

      <p v-if="shareError" class="text-sm text-bad">
        {{ shareError }}
      </p>
      <p v-if="shareSuccessMessage" class="text-sm text-ok">
        {{ shareSuccessMessage }}
      </p>
    </div>
    <template #footer>
      <div class="flex flex-wrap items-center gap-2 w-full">
        <div class="flex-grow"></div>
        <div class="flex items-center gap-2">
          <BaseButton
            v-if="shareStatus?.is_active"
            variant="danger"
            size="sm"
            :loading="shareRevoking"
            @click="handleStopSharing"
          >
            {{ t('share.stopSharing') }}
          </BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :loading="shareSaving"
            @click="handleShareSubmit"
          >
            {{
              shareStatus?.is_active
                ? t('share.updateButton')
                : t('share.createButton')
            }}
          </BaseButton>
          <BaseButton
            variant="secondary"
            size="sm"
            :disabled="shareSaving || shareRevoking"
            @click="closeShareModal"
          >
            {{ t('common.close') }}
          </BaseButton>
        </div>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps({
  share: { type: Object, required: true },
  shareStatus: { type: Object, default: null }
})

const { t } = useI18n()

// The page owns the share composable; this component only draws it.
const {
  showShareModal,
  shareForm,
  shareSaving,
  shareRevoking,
  shareError,
  shareSuccessMessage,
  sharePasswordDisplay,
  shareCopyState,
  showShareLink,
  shareExpirationOptions,
  closeShareModal,
  handleShareSubmit,
  handleStopSharing,
  generateLocalPassword,
  copyShareLink,
  copySharePassword
} = props.share
</script>
