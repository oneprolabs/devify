<template>
  <BaseModal :show="true" @close="$emit('close')">
    <div class="space-y-5">
      <div>
        <h3 class="text-lg font-semibold text-ink">
          {{ t('expense.invoices.fileAwayTitle') }}
        </h3>
        <p class="mt-1 text-sm text-ink-3">
          {{ t('expense.invoices.fileAwaySubtitle', { count }) }}
        </p>
      </div>

      <div class="space-y-2">
        <label
          v-for="option in reasons"
          :key="option"
          class="flex cursor-pointer items-center gap-3 rounded-lg border p-3"
          :class="
            reason === option
              ? 'border-accent bg-accent-soft'
              : 'border-line hover:border-line'
          "
        >
          <input
            v-model="reason"
            type="radio"
            :value="option"
            class="text-accent focus:ring-accent"
          />
          <span class="text-sm text-ink">
            {{ t(`expense.invoices.filedReasons.${option}`) }}
          </span>
        </label>
      </div>

      <p class="text-xs leading-relaxed text-ink-3">
        {{ t('expense.invoices.fileAwayNote') }}
      </p>

      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" @click="$emit('close')">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton :loading="saving" @click="$emit('confirm', reason)">
          {{ t('expense.invoices.fileAway') }}
        </BaseButton>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'

defineProps({
  count: {
    type: Number,
    default: 0
  },
  saving: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close', 'confirm'])

const { t } = useI18n()

// The reason is what makes the archive readable later: "personal" and
// "expired" are very different kinds of never-claiming this.
const reasons = ['personal', 'rejected', 'expired', 'other']
const reason = ref('personal')
</script>
