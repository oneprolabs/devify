<template>
  <BaseModal :show="true" @close="$emit('close')">
    <div class="space-y-5">
      <div>
        <h3 class="text-lg font-semibold text-gray-900">
          {{ t('expense.scan.previewTitle') }}
        </h3>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('expense.scan.previewSubtitle') }}
        </p>
      </div>

      <div v-if="loading" class="space-y-3 animate-pulse">
        <div class="h-4 w-32 rounded bg-gray-200"></div>
        <div class="h-16 rounded bg-gray-100"></div>
      </div>

      <p
        v-else-if="error"
        class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        {{ error }}
      </p>

      <template v-else-if="preview">
        <dl class="grid grid-cols-3 gap-4 rounded-lg bg-gray-50 p-4">
          <div>
            <dt class="text-xs text-gray-500">
              {{ t('expense.scan.scanned') }}
            </dt>
            <dd class="mt-1 text-lg font-semibold tabular-nums text-gray-900">
              {{ preview.emails_scanned }}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500">
              {{ t('expense.scan.candidates') }}
            </dt>
            <dd class="mt-1 text-lg font-semibold tabular-nums text-gray-900">
              {{ preview.candidate_emails }}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500">
              {{ t('expense.scan.estimatedCost') }}
            </dt>
            <dd
              class="mt-1 text-lg font-semibold tabular-nums text-primary-600"
            >
              {{ preview.estimated_credits }}
            </dd>
          </div>
        </dl>

        <p class="text-xs leading-relaxed text-gray-500">
          {{
            t('expense.scan.costNote', {
              credits: preview.cost_credits_per_email
            })
          }}
        </p>

        <p
          v-if="preview.pending_dependency_attachments"
          class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
        >
          {{
            t('expense.scan.pendingDependency', {
              count: preview.pending_dependency_attachments
            })
          }}
        </p>

        <div v-if="preview.blocked_links?.length" class="space-y-2">
          <p class="text-xs font-medium text-gray-700">
            {{
              t('expense.scan.blockedLinks', {
                count: preview.blocked_links.length
              })
            }}
          </p>
          <ul class="space-y-1">
            <li
              v-for="link in preview.blocked_links.slice(0, 5)"
              :key="link.url"
              class="truncate text-xs text-gray-500"
            >
              {{ link.url }}
            </li>
          </ul>
        </div>
      </template>

      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" @click="$emit('close')">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton
          :disabled="loading || !!error || !preview?.candidate_emails"
          @click="$emit('confirm')"
        >
          {{ t('expense.scan.confirm') }}
        </BaseButton>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'

defineProps({
  preview: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

defineEmits(['close', 'confirm'])

const { t } = useI18n()
</script>
