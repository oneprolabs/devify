<template>
  <!-- No home city, no trips: the detection needs a city to travel out from
       and no longer guesses one. Without this the card simply would not
       render and there would be nothing to tell the user why. -->
  <BaseCard v-if="!homeCity">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink">
          {{ t('expense.trips.needsHomeCityTitle') }}
        </h2>
        <p class="mt-1 max-w-prose text-sm text-ink-3">
          {{ t('expense.trips.needsHomeCityBody') }}
        </p>
      </div>
      <BaseButton size="sm" @click="$emit('configure')">
        {{ t('expense.trips.needsHomeCityAction') }}
      </BaseButton>
    </div>
  </BaseCard>

  <!-- The artboard compresses this to a band per trip rather than the card
       with a heading, a subtitle and a collapse that it used to be: a trip
       is a proposal the rules worked out, and it should not weigh more on
       the page than the invoices it is proposing to group. -->
  <div v-else-if="trips.length" class="flex flex-col gap-2">
    <div
      v-for="trip in trips"
      :key="trip.uuid"
      class="flex flex-wrap items-center gap-3 rounded-lg border border-line border-l-[3px] border-l-accent bg-panel-sub px-[13px] py-[11px]"
    >
      <svg
        class="h-[17px] w-[17px] flex-none text-accent"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.9"
        aria-hidden="true"
      >
        <path
          d="M3 12h13M12 7l5 5-5 5M19 5v14"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>

      <div class="flex min-w-0 flex-col gap-0.5">
        <div class="flex items-center gap-2">
          <span class="text-[calc(12.5px*var(--fs))] font-medium text-ink">
            {{ trip.destination_city }}
          </span>
          <span
            class="font-mono rounded-sm px-1.5 py-px text-[calc(9.5px*var(--fs))]"
            :class="
              isSure(trip) ? 'bg-ok-soft text-ok' : 'bg-warn-soft text-warn'
            "
          >
            {{
              isSure(trip)
                ? t('expense.trips.confident')
                : t('expense.trips.unsure')
            }}
          </span>
        </div>
        <span class="font-mono text-[calc(11px*var(--fs))] text-ink-3">
          {{ shortDate(trip.start_date) }} → {{ shortDate(trip.end_date) }} ·
          {{
            t('expense.trips.detail', {
              count: trip.invoice_ids.length,
              amount: trip.total_amount
            })
          }}
        </span>
      </div>

      <div class="ml-auto flex flex-none items-center gap-[7px]">
        <BaseButton size="sm" variant="outline" @click="$emit('dismiss', trip)">
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

    <!-- The artboard carries this inside the band, which works for the one
         trip it draws; with several it would repeat verbatim, so it sits
         once under the set instead. -->
    <p class="pl-4 text-[calc(11px*var(--fs))] text-ink-4">
      {{ t('expense.trips.freeNote') }}
    </p>
  </div>
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
  },
  homeCity: {
    type: String,
    default: ''
  }
})

defineEmits(['accept', 'dismiss', 'configure'])

const { t } = useI18n()

// A trip with a return leg is a trip; one without is a guess about where
// the journey ended, and saying so is more useful than a number.
function isSure(trip) {
  return Number(trip.confidence || 0) >= 0.8
}

function shortDate(value) {
  return value ? value.slice(5) : '-'
}
</script>
