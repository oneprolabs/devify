<template>
  <div class="flex h-screen overflow-hidden bg-app text-ink">
    <AppSidebar class="hidden md:flex" />

    <div class="flex min-w-0 flex-1 flex-col">
      <!-- A page that owns its header draws its own title bar, including the
           account menu on phones. Only the not-yet-converted pages need this
           app-level one. -->
      <header
        v-if="padded"
        class="flex h-[52px] flex-shrink-0 items-center justify-between border-b border-line px-4 md:hidden"
      >
        <router-link to="/chats" class="flex items-center gap-2">
          <img
            src="/android-chrome-192x192.png"
            alt=""
            class="h-[26px] w-[26px] flex-none rounded-[7px]"
          />
          <span class="font-display text-[calc(15px*var(--fs))] font-semibold text-ink">
            {{ t('common.appName') }}
          </span>
        </router-link>
        <UserMenu placement="bottom" :show-name="false" />
      </header>

      <div v-if="padded" class="min-h-0 flex-1 overflow-y-auto">
        <main
          class="max-w-7xl mx-auto w-full py-6 px-4 pb-[74px] sm:px-6 md:pb-6 lg:px-8"
        >
          <slot />
        </main>
      </div>
      <main
        v-else
        class="flex min-h-0 flex-1 flex-col overflow-hidden pb-[58px] md:pb-0"
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

defineProps({
  // The canvas puts every page in a full-bleed column with its own 56px
  // header. This flag keeps the old centred container for the pages that
  // have not been redrawn yet, and goes away with the last of them.
  padded: { type: Boolean, default: true }
})

const { t } = useI18n()
</script>
