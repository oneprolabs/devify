<template>
  <AppLayout :padded="false">
    <PageHeader
      :title="t('apps.centerTitle')"
      :count="t('apps.appCount', { count: apps.length })"
      gutter="lg"
    />

    <div class="min-h-0 flex-1 overflow-y-auto p-4 md:p-7">
      <router-link v-if="route.params.spaceId" :to="`/spaces/${route.params.spaceId}/overview`" class="mb-4 inline-block text-xs text-accent">← {{ t('apps.backToWorkspace') }}</router-link>
      <div class="flex flex-col gap-3.5 md:gap-[22px]">
        <div class="flex max-w-[720px] flex-col gap-[7px]">
          <h1
            class="font-display hidden text-[calc(22px*var(--fs))] font-semibold tracking-tight text-ink md:block"
          >
            {{ t('apps.centerHeadline') }}
          </h1>
          <p class="text-[calc(12.5px*var(--fs))] leading-[1.7] text-ink-3 md:text-[calc(13px*var(--fs))]">
            {{ t('apps.panelDescription') }}
          </p>
        </div>

        <BaseLoading v-if="loading" />

        <p v-else-if="loadError" role="alert" class="text-sm text-ink-3">{{ loadError }} <button type="button" class="text-accent" @click="loadApps">{{ t('common.refresh') }}</button></p>
        <p v-else-if="!apps.length" class="text-sm text-ink-3">{{ t('apps.noSpaceApps') }}</p>

        <div
          v-else
          class="grid max-w-[1000px] grid-cols-1 gap-3.5 md:grid-cols-2 md:gap-4"
        >
          <AppCard
            v-for="app in apps"
            :key="app.key"
            :name="appName(app)"
            :description="appDescription(app)"
            :icon="APP_ICONS[app.key] || IconApps"
            :stats="appStats(app)"
            :tags="appTags(app)"
            @open="openApp(app)"
          />
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import AppCard from '@/components/apps/AppCard.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import {
  IconApps,
  IconExpense,
  IconRelay,
  IconTodos
} from '@/components/layout/navIcons'
import { relayApi } from '@/api/relay'
import { extractErrorMessage } from '@/utils/api'
import { useToast } from '@/composables/useToast'
import { usePreferencesStore } from '@/store/preferences'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
let requestId = 0
const { showError } = useToast()
const preferences = usePreferencesStore()

const APP_ICONS = {
  relay: IconRelay,
  expense: IconExpense,
  todos: IconTodos
}

// What each app connects to. Static because it describes the integration,
// not this account's data.
const APP_TAGS = {
  relay: ['relay.targetFeishu', 'relay.targetJira', 'relay.targetGitHub']
}

// Which numbers each card shows, in the order the canvas puts them, and
// which of them is worth colouring.
const APP_STATS = {
  relay: [
    { key: 'channels', label: 'apps.statChannels' },
    { key: 'deliveries_this_week', label: 'apps.statDeliveriesThisWeek' },
    { key: 'failed', label: 'apps.statFailed', tone: 'text-bad' }
  ],
  expense: [
    { key: 'invoices', label: 'apps.statInvoices' },
    { key: 'unfiled', label: 'apps.statUnfiled', tone: 'text-warn' },
    { key: 'open_groups', label: 'apps.statOpenGroups' }
  ],
  todos: [
    { key: 'incomplete', label: 'apps.statIncomplete', tone: 'text-warn' },
    { key: 'overdue', label: 'apps.statOverdue', tone: 'text-bad' },
    {
      key: 'completion_rate',
      label: 'apps.statCompletionRate',
      suffix: '%'
    }
  ]
}

const loading = ref(false)
const apps = ref([])
const loadError = ref('')

const isChinese = computed(() => preferences.currentLanguage === 'zh-CN')

const appName = (app) => (isChinese.value && app.name_zh) || app.name

// The registry ships an English description; the locale files carry the
// wording the rest of the UI uses, so prefer those when they know the app.
const DESCRIPTION_KEYS = {
  relay: 'apps.relayDesc',
  expense: 'apps.expenseDesc',
  todos: 'apps.todoDesc'
}
const appDescription = (app) =>
  DESCRIPTION_KEYS[app.key] ? t(DESCRIPTION_KEYS[app.key]) : app.description

const appTags = (app) => (APP_TAGS[app.key] || []).map((key) => t(key))

const appStats = (app) =>
  (APP_STATS[app.key] || [])
    .filter((stat) => app.stats?.[stat.key] !== undefined)
    .map((stat) => ({
      key: stat.key,
      value: `${app.stats[stat.key]}${stat.suffix || ''}`,
      label: t(stat.label),
      // A zero is not a problem, so it stays in the default ink.
      tone: app.stats[stat.key] ? stat.tone || '' : ''
    }))

async function loadApps() {
  const current = ++requestId
  loading.value = true
  apps.value = []
  loadError.value = ''
  try {
    const data = await relayApi.getApps(route.params.spaceId)
    if (current !== requestId) return
    apps.value = Array.isArray(data) ? data : []
  } catch (error) {
    if (current === requestId) {
      loadError.value = extractErrorMessage(error, t('common.error'))
      showError(loadError.value)
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}

function openApp(app) {
  if (app?.path) router.push(app.path)
}

watch(() => route.params.spaceId, loadApps, { immediate: true })
</script>
