<template>
  <div
    class="flex flex-col overflow-hidden rounded-[11px] border border-line bg-panel"
  >
    <div
      class="flex h-[42px] flex-shrink-0 items-center gap-3 border-b border-line-soft px-5"
    >
      <span class="text-[calc(13px*var(--fs))] font-semibold text-ink">
        {{ t('billing.creditUsage.title') }}
      </span>
      <select
        v-model="selectedRange"
        class="ml-auto rounded border-line bg-panel py-1 pl-2 pr-7 font-mono text-[calc(11px*var(--fs))] text-ink-3 focus:border-accent focus:ring-0"
        @change="fetchUsageList"
      >
        <option value="7">{{ t('billing.creditUsage.last7Days') }}</option>
        <option value="30">{{ t('billing.creditUsage.last30Days') }}</option>
        <option value="90">{{ t('billing.creditUsage.last90Days') }}</option>
      </select>
    </div>

    <SkeletonRows v-if="loading" :count="4" />

    <p
      v-else-if="usageList.length === 0"
      class="py-10 text-center text-sm italic text-ink-3"
    >
      {{ t('billing.creditUsage.noData') }}
    </p>

    <template v-else>
      <!-- Which conversation spent it, how many attachments it carried, what
           it cost and when. -->
      <div
        class="flex h-8 flex-shrink-0 items-center gap-3 border-b border-line bg-panel-sub px-5 font-mono text-[calc(10px*var(--fs))] tracking-[0.06em] text-ink-4"
      >
        <div class="min-w-0 flex-1">{{ t('billing.creditUsage.chat') }}</div>
        <div class="w-24 flex-none">{{ t('chats.files.title') }}</div>
        <div class="w-20 flex-none text-right">
          {{ t('billing.creditUsage.credits') }}
        </div>
        <div class="w-[110px] flex-none text-right">
          {{ t('chats.colTime') }}
        </div>
      </div>

      <button
        v-for="item in usageList"
        :key="item.id"
        type="button"
        class="flex items-center gap-3 border-b border-line-soft px-5 py-[var(--rowpy)] text-left transition-colors last:border-b-0 hover:bg-panel-sub"
        @click="goToChat(item.chat_id)"
      >
        <span class="min-w-0 flex-1 truncate text-[calc(12.5px*var(--fs))] text-ink">
          {{
            item.display_title ||
            item.summary_title ||
            item.subject ||
            t('billing.creditUsage.noSubject')
          }}
        </span>
        <span class="w-24 flex-none font-mono text-[calc(11px*var(--fs))] text-ink-3">
          {{
            t('chats.attachmentsShort', { count: item.attachment_count || 0 })
          }}
        </span>
        <span class="w-20 flex-none text-right font-mono text-xs text-ink">
          {{ item.amount }}
        </span>
        <span
          class="w-[110px] flex-none text-right font-mono text-[calc(11px*var(--fs))] text-ink-4"
        >
          {{ formatUsageTime(item.created_at) }}
        </span>
      </button>
    </template>

    <!-- Pagination -->
    <div
      v-if="totalPages > 1"
      class="flex items-center justify-between border-t border-line pt-3 mt-3"
    >
      <button
        @click="prevPage"
        :disabled="currentPage === 1"
        class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-ink-2 bg-panel border border-line hover:bg-app-sub"
      >
        <svg
          class="w-4 h-4 mr-1"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M15 19l-7-7 7-7"
          />
        </svg>
        {{ t('common.previous') }}
      </button>

      <span class="text-xs text-ink-2">
        {{ t('common.pageInfo', { current: currentPage, total: totalPages }) }}
      </span>

      <button
        @click="nextPage"
        :disabled="currentPage === totalPages"
        class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-ink-2 bg-panel border border-line hover:bg-app-sub"
      >
        {{ t('common.next') }}
        <svg
          class="w-4 h-4 ml-1"
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
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import billingApi from '@/api/billing'
import { formatDate } from '@/utils/timezone'
import { usePreferencesStore } from '@/store/preferences'
import SkeletonRows from '@/components/ui/SkeletonRows.vue'

const { t } = useI18n()
const router = useRouter()
const preferences = usePreferencesStore()

// The canvas stamps these rows with the moment they happened, in the same
// MM-DD HH:mm the rest of the log uses, not a relative phrase.
const formatUsageTime = (value) =>
  formatDate(value, preferences.currentTimezone, 'MM-dd HH:mm')

const loading = ref(false)
const usageList = ref([])
const selectedRange = ref('30')
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 10

const fetchUsageList = async () => {
  loading.value = true
  try {
    const endDate = new Date()
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - parseInt(selectedRange.value))

    const response = await billingApi.getCreditUsageList({
      start_date: startDate.toISOString(),
      end_date: endDate.toISOString(),
      page: currentPage.value,
      page_size: pageSize
    })

    const responseData = response.data.data || response.data
    usageList.value = responseData.results || []
    totalPages.value = Math.ceil((responseData.count || 0) / pageSize)
  } catch (error) {
    console.error('Failed to fetch credit usage list:', error)
    usageList.value = []
  } finally {
    loading.value = false
  }
}

const goToChat = (chatId) => {
  if (chatId) {
    router.push(`/chats/${chatId}`)
  }
}

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    fetchUsageList()
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    fetchUsageList()
  }
}

onMounted(() => {
  fetchUsageList()
})
</script>
