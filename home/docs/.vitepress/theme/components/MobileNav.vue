<template>
  <div>
    <!-- Mobile Menu Button -->
    <button
      @click="isOpen = !isOpen"
      type="button"
      class="lg:hidden inline-flex items-center justify-center p-2 rounded-md text-gray-700 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500 min-w-[44px] min-h-[44px]"
      :aria-expanded="isOpen"
      aria-label="Toggle navigation menu"
    >
      <svg v-if="!isOpen" class="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
      </svg>
      <svg v-else class="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>

    <!-- Mobile Menu Panel -->
    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="isOpen"
        class="lg:hidden absolute top-full left-0 right-0 mt-2 mx-4 bg-white rounded-lg shadow-xl border border-gray-200 z-50"
      >
        <div class="px-4 py-6 space-y-1">
          <a
            v-for="(item, index) in navItems"
            :key="index"
            :href="item.url"
            @click="isOpen = false"
            class="block px-4 py-3 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50 transition-colors duration-200 min-h-[44px] flex items-center"
          >
            {{ item.text }}
          </a>

          <!-- Language Switcher (if provided) -->
          <div v-if="languages && languages.length > 0" class="pt-4 border-t border-gray-200 mt-4">
            <p class="px-4 text-sm font-medium text-gray-500 mb-2">
              {{ languageLabel }}
            </p>
            <a
              v-for="(lang, index) in languages"
              :key="index"
              :href="lang.url"
              @click="isOpen = false"
              class="block px-4 py-3 rounded-md text-base text-gray-700 hover:text-gray-900 hover:bg-gray-50 transition-colors duration-200 min-h-[44px] flex items-center"
            >
              {{ lang.text }}
            </a>
          </div>

          <!-- CTA Button (if provided) -->
          <div v-if="ctaButton" class="pt-4">
            <a
              :href="ctaButton.url"
              @click="isOpen = false"
              class="block w-full px-4 py-3 text-center rounded-md text-base font-medium text-white bg-primary-600 hover:bg-primary-700 transition-colors duration-200 shadow-sm min-h-[44px] flex items-center justify-center"
            >
              {{ ctaButton.text }}
            </a>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Overlay -->
    <Transition
      enter-active-class="transition-opacity ease-linear duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity ease-linear duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen"
        @click="isOpen = false"
        class="lg:hidden fixed inset-0 bg-gray-600 bg-opacity-50 z-40"
        aria-hidden="true"
      ></div>
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  navItems: {
    type: Array,
    default: () => []
  },
  languages: {
    type: Array,
    default: () => []
  },
  languageLabel: {
    type: String,
    default: 'Language'
  },
  ctaButton: {
    type: Object,
    default: null
  }
})

const isOpen = ref(false)
</script>
