<template>
  <BaseCard v-if="trips.length">
    <div class="space-y-4">
      <div>
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('expense.trips.title') }}
        </h2>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('expense.trips.subtitle') }}
        </p>
      </div>

      <div
        v-for="trip in trips"
        :key="trip.uuid"
        class="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <p class="text-sm font-medium text-gray-900">
            {{
              t('expense.trips.headline', {
                city: trip.destination_city,
                start: trip.start_date,
                end: trip.end_date
              })
            }}
          </p>
          <p class="mt-1 text-xs text-gray-500">
            {{
              t('expense.trips.detail', {
                count: trip.invoice_ids.length,
                amount: trip.total_amount
              })
            }}
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

      <p class="text-xs text-gray-500">
        {{ t('expense.trips.freeNote') }}
      </p>
    </div>
  </BaseCard>
</template>

<script setup>
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
</script>
