<template>
  <aside
    class="flex w-[232px] flex-shrink-0 flex-col border-r border-line bg-app-sub py-[18px]"
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
        {{ t('chats.title') }}
        <span
          v-if="pendingChats"
          class="ml-auto rounded-full bg-warn-soft px-[7px] py-0.5 font-mono text-[10.5px] text-warn"
        >
          {{ pendingChats }}
        </span>
      </router-link>
    </nav>

    <div class="flex flex-col px-3 pt-4">
      <router-link
        to="/apps"
        class="flex h-8 items-center gap-2.5 rounded px-3 text-ink-3 transition-colors hover:bg-chip hover:text-ink"
      >
        <IconApps class="h-[15px] w-[15px] flex-none" />
        <span class="font-display text-xs font-semibold tracking-wide">
          {{ t('apps.centerTitle') }}
        </span>
        <span class="ml-auto font-mono text-[10.5px] text-ink-4">
          {{ appLinks.length }}
        </span>
      </router-link>

      <div
        class="ml-[21px] mt-1 flex flex-col gap-0.5 border-l border-line pl-3"
      >
        <router-link
          v-for="app in appLinks"
          :key="app.to"
          :to="app.to"
          class="flex h-9 items-center gap-2.5 rounded px-2.5 text-[13px] transition-colors"
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
            class="ml-auto font-mono text-[10.5px] text-ink-4"
          >
            {{ app.count }}
          </span>
        </router-link>
      </div>
    </div>

    <div
      class="font-display px-6 pb-[7px] pt-[19px] text-[10.5px] font-semibold tracking-[0.1em] text-ink-3"
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
          <span class="text-[11.5px] text-ink-2">{{ t('nav.credits') }}</span>
          <span class="font-mono text-[12.5px] font-medium text-ink">
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

      <div class="pt-3.5">
        <UserMenu placement="top" :plan-name="planName" />
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import UserMenu from './UserMenu.vue'
import { useAccountSummary } from '@/composables/useAccountSummary'
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
  ensureLoaded
} = useAccountSummary()

const appLinks = computed(() => [
  {
    to: '/apps/relay',
    match: '/apps/relay',
    label: t('apps.relayName'),
    icon: IconRelay
  },
  {
    to: '/apps/expense',
    match: '/apps/expense',
    label: t('apps.expenseName'),
    icon: IconExpense
  },
  {
    to: '/todos',
    match: '/todos',
    label: t('todos.title'),
    icon: IconTodos,
    count: openTodos.value
  }
])

const isActive = (path) => route.path.startsWith(path)
const chatsActive = computed(() => isActive('/chats'))

const itemClass = (active) =>
  active
    ? 'bg-accent-soft text-accent'
    : 'text-ink-2 hover:bg-chip hover:text-ink'

onMounted(ensureLoaded)
</script>

<style scoped>
.nav-item {
  @apply flex h-[38px] items-center gap-2.5 rounded px-3 text-[13.5px] transition-colors;
}
</style>
