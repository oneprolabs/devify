<template>
  <div class="relative" ref="dropdownRef">
    <button
      @click="toggleDropdown"
      :class="triggerClass"
      :title="t('common.language')"
    >
      {{ currentLanguageDisplay }}
      <svg
        class="h-3 w-3"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.3"
        aria-hidden="true"
      >
        <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <!-- Dropdown menu -->
    <Transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="transform opacity-0 scale-95"
      enter-to-class="transform opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="transform opacity-100 scale-100"
      leave-to-class="transform opacity-0 scale-95"
    >
      <div
        v-if="showDropdown"
        class="absolute right-0 z-50 mt-2 w-32 rounded-md border border-line bg-panel py-1 shadow-lg"
      >
        <button
          v-for="lang in languages"
          :key="lang.value"
          @click="selectLanguage(lang.value)"
          class="flex w-full items-center px-3 py-1.5 text-[calc(12.5px*var(--fs))] text-ink-2 transition-colors hover:bg-chip"
          :class="{ 'bg-app-sub font-medium': locale === lang.value }"
        >
          <span class="mr-2 text-[calc(12.5px*var(--fs))]">{{ lang.flag }}</span>
          {{ lang.label }}
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import i18n from '@/i18n'

const props = defineProps({
  variant: {
    type: String,
    default: 'light'
  }
})

const { t, locale } = useI18n()

const showDropdown = ref(false)
const dropdownRef = ref(null)

const languages = [
  { value: 'en', label: 'English', flag: '🇺🇸' },
  { value: 'zh-CN', label: '简体中文', flag: '🇨🇳' },
  { value: 'es', label: 'Español', flag: '🇪🇸' }
]

const currentLanguageDisplay = computed(() => {
  const lang = languages.find((l) => l.value === locale.value)
  return lang ? lang.label : '🌐'
})

const triggerClass = computed(() => {
  return props.variant === 'dark'
    ? 'flex items-center gap-[5px] text-xs text-ink-4 transition-colors hover:text-accent-on'
    : 'flex items-center gap-[5px] text-xs text-ink-3 transition-colors hover:text-ink-2'
})

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value
}

const selectLanguage = (language) => {
  // Only update UI display language, do not sync to AI prompt language
  locale.value = language
  i18n.global.locale.value = language
  localStorage.setItem('userLanguage', language)
  showDropdown.value = false
}

const handleClickOutside = (event) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target)) {
    showDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>
