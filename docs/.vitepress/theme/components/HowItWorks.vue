<template>
  <div class="how-it-works-wrapper relative py-16 md:py-24 overflow-hidden">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
      <!-- Section Header -->
      <div class="text-center mb-12 md:mb-16">
        <h2 class="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-900 mb-4">
          <span class="md:hidden whitespace-pre-line">{{ formattedTitleMobile }}</span>
          <span class="hidden md:inline">{{ formattedTitle }}</span>
        </h2>
        <p class="text-lg md:text-xl text-gray-600 max-w-3xl mx-auto">
          {{ subtitle }}
        </p>
      </div>

      <!-- Steps -->
      <div :class="['grid grid-cols-1 gap-8 md:gap-12 relative', steps.length === 4 ? 'md:grid-cols-4' : 'md:grid-cols-3']">
        <!-- Connection lines for desktop -->
        <div
          class="hidden md:block absolute top-10 left-0 right-0 h-0.5 bg-gradient-to-r from-primary-200 via-primary-400 to-primary-200"
          :style="steps.length === 4 ? 'width: 75%; margin-left: 12.5%;' : 'width: 66%; margin-left: 17%;'"
        ></div>

        <div
          v-for="(step, index) in steps"
          :key="index"
          class="relative flex flex-col items-center text-center"
        >
          <!-- Step number circle -->
          <div class="relative z-10 mb-6">
            <div class="w-20 h-20 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-lg">
              <!-- Icon -->
              <svg v-if="step.icon === 'email'" class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              <svg v-else-if="step.icon === 'ai'" class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <svg v-else-if="step.icon === 'dashboard'" class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <svg v-else-if="step.icon === 'integration'" class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
              </svg>
              <svg v-else class="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
            </div>

            <!-- Step number badge -->
            <div class="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-white border-2 border-primary-500 flex items-center justify-center text-sm font-bold text-primary-600 shadow">
              {{ index + 1 }}
            </div>
          </div>

          <!-- Content -->
          <h3 class="text-xl md:text-2xl font-semibold text-gray-900 mb-3">
            {{ step.title }}
          </h3>
          <p class="text-gray-600 leading-relaxed max-w-sm">
            {{ step.description }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  },
  steps: {
    type: Array,
    required: true
  }
})

// Format title for PC (single line, no line breaks)
const formattedTitle = computed(() => {
  return props.title.replace(/\n/g, '')
})

// Format title for mobile (with line break after "简单三步")
const formattedTitleMobile = computed(() => {
  const title = props.title.replace(/\n/g, '')
  // Insert line break after "简单三步"
  if (title.includes('简单三步')) {
    return title.replace('简单三步', '简单三步\n')
  }
  return title
})
</script>

<style scoped>
.how-it-works-wrapper {
  position: relative;
  background: #f8fafc;
}

</style>
