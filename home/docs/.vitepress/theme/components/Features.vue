<template>
  <div id="features" class="features-wrapper relative py-16 md:py-24 overflow-hidden">
    <!-- Background pattern -->
    <div class="features-background"></div>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
      <!-- Section Header -->
      <div class="text-center mb-12 md:mb-16">
        <h2 class="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-900 mb-4">
          {{ title }}
        </h2>
        <p class="text-lg md:text-xl text-gray-600 max-w-3xl mx-auto">
          {{ subtitle }}
        </p>
      </div>

      <!-- Features Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-8 md:gap-10">
        <div
          v-for="(feature, index) in features"
          :key="index"
          class="feature-card group"
        >
          <!-- Icon and Title in a flex container -->
          <div class="flex items-center gap-3 mb-3">
            <!-- Icon -->
            <div class="flex-shrink-0 inline-flex items-center justify-center w-12 h-12 sm:w-14 sm:h-14 rounded-lg bg-primary-100 text-primary-600 group-hover:bg-primary-600 group-hover:text-white transition-colors duration-200">
              <svg v-if="feature.icon === 'backup'" class="w-6 h-6 sm:w-7 sm:h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
              </svg>
              <svg v-else-if="feature.icon === 'image'" class="w-6 h-6 sm:w-7 sm:h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <svg v-else-if="feature.icon === 'ai'" class="w-6 h-6 sm:w-7 sm:h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <svg v-else-if="feature.icon === 'search'" class="w-6 h-6 sm:w-7 sm:h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <svg v-else-if="feature.icon === 'integration'" class="w-6 h-6 sm:w-7 sm:h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
              </svg>
              <svg v-else-if="feature.icon === 'analytics'" class="w-6 h-6 sm:w-7 sm:h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <svg v-else class="w-6 h-6 sm:w-7 sm:h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
            </div>

            <!-- Title -->
            <h3 class="text-lg sm:text-xl font-semibold text-gray-900 flex-1 leading-tight">
              {{ feature.title }}
            </h3>
          </div>

          <!-- Description -->
          <p class="text-gray-600 leading-relaxed">
            {{ feature.description }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  },
  features: {
    type: Array,
    required: true
  }
})
</script>

<style scoped>
.features-wrapper {
  background: #ffffff;
}

.features-background {
  position: absolute;
  inset: 0;
  opacity: 0.4;
  background-image:
    radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.05) 0%, transparent 50%),
    radial-gradient(circle at 80% 70%, rgba(168, 85, 247, 0.05) 0%, transparent 50%);
  z-index: 0;
}

.feature-card {
  padding: 2rem;
  border-radius: 0.75rem;
  background: white;
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.feature-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  transform: scaleX(0);
  transition: transform 0.3s ease;
}

.feature-card:hover::before {
  transform: scaleX(1);
}

.feature-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 20px 40px -10px rgba(99, 102, 241, 0.2), 0 10px 20px -5px rgba(168, 85, 247, 0.1);
  border-color: #c7d2fe;
}

@media (max-width: 640px) {
  .feature-card {
    padding: 1.5rem;
  }
}
</style>
