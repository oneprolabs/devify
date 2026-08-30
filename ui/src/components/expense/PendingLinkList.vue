<template>
  <BaseCard v-if="links.length">
    <div class="space-y-4">
      <div>
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('expense.links.title') }}
        </h2>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('expense.links.subtitle') }}
        </p>
      </div>

      <ul class="divide-y divide-gray-100">
        <li
          v-for="link in links"
          :key="link.uuid"
          class="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div class="min-w-0 space-y-1">
            <p class="truncate text-sm text-gray-900" :title="link.source_url">
              {{ link.source_url }}
            </p>
            <p class="text-xs text-gray-500">
              {{ t(`expense.links.reasons.${link.fetch_status}`) }}
            </p>
          </div>

          <BaseButton
            v-if="canRelease(link)"
            size="sm"
            variant="outline"
            :loading="releasing === link.uuid"
            @click="$emit('release', link)"
          >
            {{ t('expense.links.release') }}
          </BaseButton>
        </li>
      </ul>

      <p class="text-xs leading-relaxed text-gray-500">
        {{ t('expense.links.safetyNote') }}
      </p>
    </div>
  </BaseCard>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'

defineProps({
  links: {
    type: Array,
    default: () => []
  },
  releasing: {
    type: String,
    default: ''
  }
})

defineEmits(['release'])

const { t } = useI18n()

// Only a domain that was refused can be released by hand. A link that
// needs a login, or resolved somewhere private, is not a decision the
// user can override from here.
function canRelease(link) {
  return link.fetch_status === 'blocked_domain' && !link.user_allowed
}
</script>
