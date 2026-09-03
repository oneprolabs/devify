<template>
  <div class="flex min-h-screen bg-app text-ink">
    <AppSidebar class="hidden md:flex" />

    <div class="flex min-w-0 flex-1 flex-col">
      <header
        class="flex h-[52px] flex-shrink-0 items-center justify-between border-b border-line px-4 md:hidden"
      >
        <router-link to="/chats" class="flex items-center gap-2">
          <span
            class="flex h-[26px] w-[26px] items-center justify-center rounded-[7px] bg-accent text-accent-on"
          >
            <IconChats class="h-[15px] w-[15px]" />
          </span>
          <span class="font-display text-[15px] font-semibold text-ink">
            {{ t('common.appName') }}
          </span>
        </router-link>
        <UserMenu placement="bottom" :show-name="false" />
      </header>

      <main
        class="max-w-7xl mx-auto w-full py-6 px-4 pb-[74px] sm:px-6 md:pb-6 lg:px-8"
      >
        <slot />
      </main>
    </div>

    <AppMobileNav />
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppSidebar from './AppSidebar.vue'
import AppMobileNav from './AppMobileNav.vue'
import UserMenu from './UserMenu.vue'
import { IconChats } from './navIcons'

const { t } = useI18n()
</script>
