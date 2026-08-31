<template>
  <BaseCard v-if="trips.length">
    <div class="space-y-3">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('expense.trips.title', { count: trips.length }) }}
          </h2>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('expense.trips.subtitle') }}
          </p>
        </div>
        <BaseButton size="sm" variant="secondary" @click="open = !open">
          {{ open ? t('common.collapse') : t('common.expand') }}
        </BaseButton>
      </div>

      <!-- Several trips are the normal case, not an edge one: each is its
           own row with its own decision, so accepting one leaves the rest
           exactly as they were. -->
      <div
        v-if="open"
        class="divide-y divide-gray-100 border-t border-gray-100"
      >
        <div
          v-for="trip in trips"
          :key="trip.uuid"
          class="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div class="min-w-0">
            <p class="text-sm font-medium text-gray-900">
              {{ trip.destination_city }}
              <span class="ml-2 text-xs tabular-nums text-gray-500">
                {{ shortDate(trip.start_date) }} →
                {{ shortDate(trip.end_date) }}
              </span>
            </p>
            <p class="mt-1 text-xs text-gray-500">
              {{
                t('expense.trips.detail', {
                  count: trip.invoice_ids.length,
                  amount: trip.total_amount
                })
              }}
              ·
              <span
                :class="isSure(trip) ? 'text-emerald-600' : 'text-amber-600'"
              >
                {{
                  isSure(trip)
                    ? t('expense.trips.confident')
                    : t('expense.trips.unsure')
                }}
              </span>
            </p>
          </div>

          <div class="flex gap-2">
            <BaseButton
              size="sm"
              variant="outline"
              @click="$emit('dismiss', trip)"
            >
              {{ t('expense.trips.dismiss') }}
            </BaseButton>
            <BaseButton
              size="sm"
              :loading="accepting === trip.uuid"
              @click="$emit('accept', trip)"
            >
              {{ t('expense.trips.accept') }}
            </BaseButton>
          </div>
        </div>
      </div>

      <p v-if="open" class="text-xs text-gray-500">
        {{ t('expense.trips.freeNote') }}
      </p>
    </div>
  </BaseCard>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'

defineProps({
  trips: {
    type: Array,
    default: () => []
  },
  accepting: {
    type: String,
    default: ''
  }
})

defineEmits(['accept', 'dismiss'])

const { t } = useI18n()
const open = ref(true)

// A trip with a return leg is a trip; one without is a guess about where
// the journey ended, and saying so is more useful than a number.
function isSure(trip) {
  return Number(trip.confidence || 0) >= 0.8
}

function shortDate(value) {
  return value ? value.slice(5) : '-'
}
</script>
