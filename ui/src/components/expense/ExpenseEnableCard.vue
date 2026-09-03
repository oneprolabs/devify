<template>
  <BaseCard>
    <div class="space-y-5">
      <div
        class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
      >
        <div class="space-y-1">
          <h2 class="text-lg font-semibold text-ink">
            {{ t('expense.enableTitle') }}
          </h2>
          <p class="max-w-xl text-sm text-ink-3">
            {{ t('expense.enableDesc') }}
          </p>
        </div>

        <button
          type="button"
          role="switch"
          :aria-checked="modelValue.enabled"
          :disabled="saving"
          class="relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          :class="modelValue.enabled ? 'bg-accent' : 'bg-chip'"
          @click="$emit('toggle', !modelValue.enabled)"
        >
          <span
            class="inline-block h-4 w-4 transform rounded-full bg-panel transition-transform"
            :class="modelValue.enabled ? 'translate-x-6' : 'translate-x-1'"
          ></span>
        </button>
      </div>

      <!-- Stating the price next to the switch is a hard requirement: the
           user must know what a scan costs before turning it on. -->
      <div class="rounded-lg border border-line bg-app-sub p-4">
        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-ink-3">
              {{ t('expense.priceLabel') }}
            </dt>
            <dd class="mt-1 text-sm text-ink">
              {{ t('expense.priceValue', { credits: costPerEmail }) }}
            </dd>
          </div>
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-ink-3">
              {{ t('expense.balanceLabel') }}
            </dt>
            <dd class="mt-1 text-sm tabular-nums text-ink">
              {{ modelValue.credits_balance ?? '-' }}
            </dd>
          </div>
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-ink-3">
              {{ t('expense.lastScanLabel') }}
            </dt>
            <dd class="mt-1 text-sm text-ink">
              {{ lastScannedText }}
            </dd>
          </div>
        </dl>
        <p class="mt-3 text-xs leading-relaxed text-ink-3">
          {{ t('expense.billingNote') }}
        </p>
      </div>

      <p v-if="modelValue.enabled" class="text-xs text-ink-3">
        {{ t('expense.scanFloorNote', { time: enabledAtText }) }}
      </p>
    </div>
  </BaseCard>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/ui/BaseCard.vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  },
  saving: {
    type: Boolean,
    default: false
  }
})

defineEmits(['toggle'])

const { t, locale } = useI18n()

const costPerEmail = computed(
  () => props.modelValue.cost_credits_per_email ?? 1
)

function formatTime(value) {
  if (!value) return null
  return new Date(value).toLocaleString(locale.value)
}

const lastScannedText = computed(
  () => formatTime(props.modelValue.last_scanned_at) ?? t('expense.never')
)

const enabledAtText = computed(
  () => formatTime(props.modelValue.enabled_at) ?? ''
)
</script>
