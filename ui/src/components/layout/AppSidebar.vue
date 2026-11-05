<template>
  <aside
    class="flex w-[233px] flex-shrink-0 flex-col border-r border-line bg-app-sub py-[18px]"
  >
    <router-link to="/chats" class="flex items-center gap-2.5 px-5 pb-5">
      <img
        src="/android-chrome-192x192.png"
        alt=""
        class="h-[26px] w-[26px] flex-none rounded-[7px]"
      />
      <span
        class="font-display text-base font-semibold tracking-tight text-ink"
      >
        {{ t('common.appName') }}
      </span>
    </router-link>

    <nav class="flex flex-col gap-0.5 px-3">
      <router-link to="/chats" class="nav-item" :class="itemClass(chatsActive)">
        <IconChats class="h-[17px] w-[17px] flex-none" />
        {{ t('spaces.mailConversations') }}
        <span
          v-if="pendingChats"
          class="ml-auto rounded-full bg-warn-soft px-[7px] py-0.5 font-mono text-[calc(10.5px*var(--fs))] text-warn"
        >
          {{ pendingChats }}
        </span>
      </router-link>
      <button
        type="button"
        class="nav-parent"
        :class="{ 'is-active': workspaceActive }"
        :aria-expanded="treeOpen"
        @click="treeOpen = !treeOpen"
      >
        <IconApps class="h-[17px] w-[17px] flex-none" />
        {{ t('spaces.personalWorkspace') }}
        <span class="nav-chevron" :class="{ open: treeOpen }" aria-hidden="true"
          >▾</span
        >
      </button>
      <div v-if="treeOpen" class="nav-tree">
        <router-link
          :to="workspacePath"
          class="tree-item"
          :class="
            itemClass(
              route.name === 'SpaceOverview' ||
                (route.name === 'PersonalWorkspace' &&
                  route.query.view !== 'chats')
            )
          "
          >概览</router-link
        >
        <router-link
          :to="conversationPath"
          class="tree-item"
          :class="
            itemClass(
              route.name === 'SpaceChats' ||
                (route.name === 'PersonalWorkspace' &&
                  route.query.view === 'chats')
            )
          "
          >会话</router-link
        >
        <router-link
          :to="analysisPath"
          class="tree-item"
          :class="
            itemClass(
              route.name === 'SpaceAnalysis' &&
                !route.query.tab &&
                !route.query.panel
            )
          "
          >事件</router-link
        >
        <router-link
          :to="topicsPath"
          class="tree-item"
          :class="itemClass(route.name === 'SpaceTopics')"
          >主题订阅</router-link
        >
        <router-link
          :to="reportPath"
          class="tree-item"
          :class="
            itemClass(
              route.name === 'SpaceAnalysis' && route.query.tab === 'reports'
            )
          "
          >报告</router-link
        >
        <router-link
          :to="askPath"
          class="tree-item"
          :class="
            itemClass(
              route.name === 'SpaceAnalysis' && route.query.panel === 'ask'
            )
          "
          >问答</router-link
        >
        <router-link
          :to="syncPath"
          class="tree-item"
          :class="itemClass(route.name === 'SpaceOperations')"
          >同步记录</router-link
        >
        <router-link
          :to="settingsPath"
          class="tree-item"
          :class="itemClass(route.name === 'SpaceSettings')"
          >设备与设置</router-link
        >
      </div>
    </nav>

    <div class="flex flex-col px-3 pt-4">
      <div class="app-center-head">
        <router-link :to="appCenterPath" class="app-center-link">
          <IconApps class="h-[15px] w-[15px] flex-none" />
          <span class="font-display text-xs font-semibold tracking-wide">
            {{ t('apps.centerTitle') }}
          </span>
          <span
            class="ml-auto font-mono text-[calc(10.5px*var(--fs))] text-ink-4"
          >
            {{ appLinks.length }}
          </span>
        </router-link>
        <button
          type="button"
          class="app-center-toggle"
          :class="{ open: appCenterOpen }"
          :aria-expanded="appCenterOpen"
          aria-label="展开应用中心"
          @click="appCenterOpen = !appCenterOpen"
        >
          <span aria-hidden="true">▾</span>
        </button>
      </div>

      <Transition name="app-tree">
        <div v-show="appCenterOpen" class="app-tree">
          <router-link
            v-for="app in appLinks"
            :key="app.to"
            :to="app.to"
            class="flex h-9 items-center gap-2.5 rounded px-2.5 text-[calc(13px*var(--fs))] transition-colors"
            :class="
              isActive(app.match)
                ? 'bg-accent-soft text-accent'
                : 'text-ink-2 hover:bg-chip hover:text-ink'
            "
          >
            <component :is="app.icon" class="h-4 w-4 flex-none" />
            {{ app.label }}
            <span
              v-if="app.count"
              class="ml-auto font-mono text-[calc(10.5px*var(--fs))] text-ink-4"
            >
              {{ app.count }}
            </span>
          </router-link>
        </div>
      </Transition>
    </div>

    <div
      class="font-display px-6 pb-[7px] pt-[19px] text-[calc(10.5px*var(--fs))] font-semibold tracking-[0.1em] text-ink-3"
    >
      {{ t('nav.account') }}
    </div>
    <nav class="flex flex-col gap-0.5 px-3">
      <router-link
        to="/settings"
        class="nav-item"
        :class="itemClass(isActive('/settings'))"
      >
        <IconSettings class="h-[17px] w-[17px] flex-none" />
        {{ t('common.settings') }}
      </router-link>
      <router-link
        to="/billing"
        class="nav-item"
        :class="itemClass(isActive('/billing'))"
      >
        <IconBilling class="h-[17px] w-[17px] flex-none" />
        {{ t('billing.menuTitle') }}
      </router-link>
    </nav>

    <div class="mt-auto px-3">
      <div
        v-if="totalCredits"
        class="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3"
      >
        <div class="flex items-baseline justify-between">
          <span class="text-[calc(11.5px*var(--fs))] text-ink-2">{{
            t('nav.credits')
          }}</span>
          <span
            class="font-mono text-[calc(12.5px*var(--fs))] font-medium text-ink"
          >
            {{ availableCredits
            }}<span class="text-ink-3"> / {{ totalCredits }}</span>
          </span>
        </div>
        <div class="h-1 rounded bg-chip">
          <div
            class="h-1 rounded bg-accent"
            :style="{ width: `${creditsPercentage}%` }"
          ></div>
        </div>
      </div>

      <div class="pb-0.5 pt-3.5">
        <UserMenu placement="top" :plan-name="planName" />
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import UserMenu from './UserMenu.vue'
import { useAccountSummary } from '@/composables/useAccountSummary'
import { loadScopedApps, useScopedApps } from '@/composables/sidebarApps'
import {
  IconApps,
  IconBilling,
  IconChats,
  IconExpense,
  IconRelay,
  IconSettings,
  IconTodos
} from './navIcons'

const { t } = useI18n()
const route = useRoute()

const {
  planName,
  availableCredits,
  totalCredits,
  creditsPercentage,
  pendingChats,
  openTodos,
  unfiledInvoices,
  ensureLoaded
} = useAccountSummary()

const workspacePath = computed(() =>
  route.params.spaceId
    ? `/spaces/${route.params.spaceId}/overview`
    : '/workspace'
)
const conversationPath = computed(() =>
  route.params.spaceId
    ? `/spaces/${route.params.spaceId}/chats`
    : { path: '/workspace', query: { view: 'chats' } }
)
const analysisPath = computed(() =>
  route.params.spaceId
    ? `/spaces/${route.params.spaceId}/analysis`
    : '/workspace'
)
const reportPath = computed(() =>
  route.params.spaceId
    ? `/spaces/${route.params.spaceId}/analysis?tab=reports`
    : '/workspace'
)
const askPath = computed(() =>
  route.params.spaceId
    ? `/spaces/${route.params.spaceId}/analysis?panel=ask`
    : '/workspace'
)
const syncPath = computed(() =>
  route.params.spaceId
    ? `/spaces/${route.params.spaceId}/operations`
    : '/workspace'
)
const settingsPath = computed(() =>
  route.params.spaceId
    ? `/spaces/${route.params.spaceId}/settings`
    : '/workspace'
)
const topicsPath = computed(() =>
  route.params.spaceId ? `/spaces/${route.params.spaceId}/topics` : '/workspace'
)
const readSidebarOpen = (key, fallback) => {
  try {
    const stored = localStorage.getItem(key)
    return stored === null ? fallback : stored === '1'
  } catch {
    return fallback
  }
}

const persistSidebarOpen = (key, value) => {
  try {
    localStorage.setItem(key, value ? '1' : '0')
  } catch {
    // A blocked storage API must not break navigation.
  }
}

const treeOpen = ref(readSidebarOpen('devify.sidebar.workspaceOpen', true))
const appCenterOpen = ref(readSidebarOpen('devify.sidebar.appCenterOpen', true))
watch(treeOpen, (value) =>
  persistSidebarOpen('devify.sidebar.workspaceOpen', value)
)
watch(appCenterOpen, (value) =>
  persistSidebarOpen('devify.sidebar.appCenterOpen', value)
)
const workspaceActive = computed(() =>
  [
    'SpaceOverview',
    'SpaceChats',
    'SpaceAnalysis',
    'SpaceTopics',
    'SpaceOperations',
    'SpaceSettings',
    'PersonalWorkspace'
  ].includes(route.name)
)
const appCache = useScopedApps()
const scopedApps = computed(
  () => appCache.value[String(route.params.spaceId)] || []
)
const appCenterPath = computed(() =>
  route.params.spaceId ? `/spaces/${route.params.spaceId}/apps` : '/apps'
)
watch(
  () => route.params.spaceId,
  (spaceId) => {
    void loadScopedApps(spaceId)
  },
  { immediate: true }
)
const appLinks = computed(() =>
  [
    {
      key: 'relay',
      to: '/apps/relay',
      match: '/apps/relay',
      label: t('apps.relayName'),
      icon: IconRelay
    },
    {
      key: 'expense',
      to: '/apps/expense',
      match: '/apps/expense',
      label: t('apps.expenseName'),
      icon: IconExpense,
      count: unfiledInvoices.value
    },
    {
      key: 'todos',
      to: '/todos',
      match: '/todos',
      label: t('todos.title'),
      icon: IconTodos,
      count: openTodos.value
    }
  ].filter(
    (app) =>
      !route.params.spaceId ||
      scopedApps.value.some((item) => item.key === app.key)
  )
)

const isActive = (path) => route.path.startsWith(path)
const chatsActive = computed(() => isActive('/chats') && !route.params.spaceId)

const itemClass = (active) =>
  active
    ? 'bg-accent-soft text-accent'
    : 'text-ink-2 hover:bg-chip hover:text-ink'

onMounted(ensureLoaded)
</script>

<style scoped>
.nav-tree {
  margin: 2px 0 4px 21px;
  padding-left: 12px;
  border-left: 1px solid rgb(var(--c-line));
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.tree-item {
  @apply flex h-8 items-center rounded px-2.5 text-[calc(13px*var(--fs))] text-ink-2 transition-colors;
}
.nav-parent {
  @apply flex h-[38px] items-center gap-2.5 rounded px-3 text-left text-[calc(13.5px*var(--fs))] text-ink transition-colors hover:bg-chip;
}
.nav-parent.is-active {
  @apply bg-accent-soft text-accent;
}
.nav-chevron {
  margin-left: auto;
  color: rgb(var(--c-tx3));
  font-size: 11px;
  transform: rotate(-90deg);
  transition: transform 0.15s ease;
}
.nav-chevron.open {
  transform: none;
}
.nav-item {
  @apply flex h-[38px] items-center gap-2.5 rounded px-3 text-[calc(13.5px*var(--fs))] transition-colors;
}
.app-center-head {
  display: flex;
  align-items: center;
  gap: 2px;
}
.app-center-link {
  display: flex;
  height: 32px;
  flex: 1;
  min-width: 0;
  align-items: center;
  gap: 10px;
  border-radius: 6px;
  padding: 0 12px;
  color: rgb(var(--c-tx3));
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}
.app-center-link:hover {
  background: rgb(var(--c-chip));
  color: rgb(var(--c-tx));
}
.app-center-toggle {
  display: flex;
  width: 20px;
  height: 32px;
  flex: none;
  align-items: center;
  justify-content: center;
  color: rgb(var(--c-tx3));
  font-size: 11px;
  transform: rotate(-90deg);
  transition: transform 0.15s ease;
}
.app-center-toggle.open {
  transform: none;
}
.app-tree {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 4px 0 0 21px;
  padding-left: 12px;
  border-left: 1px solid rgb(var(--c-line));
  overflow: hidden;
}
.app-tree-enter-active,
.app-tree-leave-active {
  transition:
    max-height 0.18s ease,
    opacity 0.18s ease;
}
.app-tree-enter-from,
.app-tree-leave-to {
  max-height: 0;
  opacity: 0;
}
.app-tree-enter-to,
.app-tree-leave-from {
  max-height: 1000px;
  opacity: 1;
}
</style>
