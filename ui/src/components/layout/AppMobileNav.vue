<template>
  <nav
    class="fixed inset-x-0 bottom-0 z-40 flex h-[58px] border-t border-line bg-app-sub md:hidden"
  >
    <router-link
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      class="flex flex-1 flex-col items-center justify-center gap-[3px] transition-colors"
      :class="isActive(tab) ? 'text-accent' : 'text-ink-3'"
    >
      <component :is="tab.icon" class="h-[19px] w-[19px]" />
      <span class="text-[calc(10px*var(--fs))]">{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { IconApps, IconChats, IconSettings } from './navIcons'

const { t } = useI18n()
const route = useRoute()

const tabs = computed(() => [
  {
    to: '/chats',
    match: ['/chats'],
    label: t('nav.tabChats'),
    icon: IconChats
  },
  {
    to: '/apps',
    match: ['/apps', '/todos'],
    label: t('nav.tabApps'),
    icon: IconApps
  },
  {
    to: '/settings',
    match: ['/settings', '/billing'],
    label: t('nav.tabSettings'),
    icon: IconSettings
  }
])

const isActive = (tab) => tab.match.some((path) => route.path.startsWith(path))
</script>
