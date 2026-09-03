<template>
  <div class="relative" ref="rootRef">
    <button
      type="button"
      class="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-chip focus:outline-none focus:ring-2 focus:ring-accent"
      @click.stop="open = !open"
    >
      <span
        class="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-chip text-xs text-ink-2"
      >
        {{ userInitial }}
      </span>
      <span v-if="showName" class="flex min-w-0 flex-col">
        <span class="truncate text-[12.5px] font-medium text-ink">
          {{ displayName }}
        </span>
        <span class="truncate text-[11px] text-ink-3">{{ planName }}</span>
      </span>
    </button>

    <Transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="transform opacity-0 scale-95"
      enter-to-class="transform opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="transform opacity-100 scale-100"
      leave-to-class="transform opacity-0 scale-95"
    >
      <div
        v-if="open"
        class="absolute z-50 w-72 rounded-xl border border-line bg-panel p-2 shadow-soft-lg"
        :class="
          placement === 'top'
            ? 'bottom-full left-0 mb-2'
            : 'right-0 top-full mt-2'
        "
      >
        <div class="px-2 py-1.5">
          <div class="truncate text-sm font-semibold text-ink">
            {{ displayName }}
          </div>
          <div class="truncate text-xs text-ink-3">{{ planName }}</div>
        </div>

        <div
          v-if="virtualEmail"
          class="mt-1 rounded-lg border border-line bg-panel-sub p-2.5"
        >
          <div class="mb-1.5 text-[11px] text-ink-3">
            {{ t('virtualEmail.yourAddress') }}
          </div>
          <div class="flex items-center gap-2">
            <span
              class="min-w-0 flex-1 truncate font-mono text-[12.5px] text-ink"
              :title="virtualEmail"
            >
              {{ virtualEmail }}
            </span>
            <button
              type="button"
              class="flex-shrink-0 rounded-md p-1.5 text-ink-3 transition-colors hover:bg-chip hover:text-ink"
              :title="t('settings.copyEmail')"
              @click.stop="copyVirtualEmail"
            >
              <svg
                v-if="!copied"
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
              <svg
                v-else
                class="h-4 w-4 text-ok"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </button>
          </div>
        </div>

        <div class="my-2 border-t border-line-soft"></div>

        <div class="flex items-center justify-between px-2 py-1.5">
          <span class="text-xs text-ink-2">{{ t('theme.label') }}</span>
          <ThemeSwitcher />
        </div>
        <div class="flex items-center justify-between px-2 py-1.5">
          <span class="text-xs text-ink-2">{{ t('common.language') }}</span>
          <LanguageSwitcher />
        </div>

        <div class="my-2 border-t border-line-soft"></div>

        <router-link
          to="/settings"
          class="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-ink-2 transition-colors hover:bg-chip hover:text-ink"
          @click="open = false"
        >
          {{ t('common.settings') }}
        </router-link>
        <router-link
          v-if="isAdmin"
          to="/management/users"
          class="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-ink-2 transition-colors hover:bg-chip hover:text-ink"
          @click="open = false"
        >
          {{ t('management.adminConsole') }}
        </router-link>
        <button
          type="button"
          class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-ink-2 transition-colors hover:bg-chip hover:text-ink"
          @click="handleLogout"
        >
          {{ t('common.logout') }}
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import LanguageSwitcher from '@/components/ui/LanguageSwitcher.vue'
import ThemeSwitcher from '@/components/ui/ThemeSwitcher.vue'

defineProps({
  placement: {
    type: String,
    default: 'top'
  },
  showName: {
    type: Boolean,
    default: true
  },
  planName: {
    type: String,
    default: ''
  }
})

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()

const open = ref(false)
const copied = ref(false)
const rootRef = ref(null)

const displayName = computed(() => {
  const userInfo = userStore.userInfo
  if (!userInfo) return 'User'
  if (userInfo.display_name) return userInfo.display_name
  if (userInfo.first_name && userInfo.last_name) {
    return `${userInfo.first_name} ${userInfo.last_name}`
  }
  if (userInfo.first_name) return userInfo.first_name
  return userInfo.username || 'User'
})

const userInitial = computed(
  () => displayName.value.trim().charAt(0).toUpperCase() || 'U'
)

const virtualEmail = computed(() => userStore.userInfo?.virtual_email || '')

const isAdmin = computed(() =>
  Boolean(userStore.userInfo?.is_staff || userStore.userInfo?.is_superuser)
)

const copyVirtualEmail = async () => {
  if (!virtualEmail.value) return
  try {
    await navigator.clipboard.writeText(virtualEmail.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (error) {
    console.error('Failed to copy email:', error)
  }
}

const handleLogout = async () => {
  try {
    await userStore.logout()
  } catch (error) {
    console.error('Logout failed:', error)
  } finally {
    open.value = false
    router.push('/login')
  }
}

const handleClickOutside = (event) => {
  if (rootRef.value && !rootRef.value.contains(event.target)) {
    open.value = false
    copied.value = false
  }
}

onMounted(async () => {
  document.addEventListener('click', handleClickOutside)

  // After OAuth setup the cached user info can still be missing the AI inbox
  // address the menu shows, so refresh once when it is absent.
  if (userStore.user && !userStore.userInfo?.virtual_email) {
    await userStore.checkAuthStatus()
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>
