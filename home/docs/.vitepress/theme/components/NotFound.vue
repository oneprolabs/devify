<template>
  <div class="not-found-wrapper min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 dark:from-gray-900 dark:via-blue-900 dark:to-purple-900">
    <div class="max-w-2xl mx-auto px-6 py-12 text-center relative">
      <!-- Floating particles animation -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          v-for="(pos, i) in particlePositions"
          :key="i"
          class="particle absolute rounded-full"
          :style="pos"
        ></div>
      </div>

      <!-- Main content -->
      <div class="relative z-10">
        <!-- 404 Number with style -->
        <div class="mb-8">
          <h1 class="text-8xl md:text-9xl font-light text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 dark:from-blue-400 dark:via-purple-400 dark:to-pink-400 tracking-tight">
            404
          </h1>
        </div>

        <!-- Philosophical quote -->
        <div class="mb-8 space-y-6">
          <div class="text-2xl md:text-3xl font-light text-gray-700 dark:text-gray-300 italic leading-relaxed">
            <p v-if="isChinese" class="mb-4">
              "我们所寻找的，往往不在我们期望的地方。"
            </p>
            <p v-else class="mb-4">
              "What we seek is often not where we expect it to be."
            </p>
          </div>

          <div class="text-lg md:text-xl text-gray-500 dark:text-gray-400 font-light">
            <p v-if="isChinese">
              页面已迷失，但真理依然存在。每一次迷路，都是一次重新发现自我的机会。
            </p>
            <p v-else>
              The page is lost, but truth remains. Every detour is an opportunity to rediscover yourself.
            </p>
          </div>
        </div>

        <!-- Decorative line -->
        <div class="flex items-center justify-center gap-4 mb-8">
          <div class="h-px w-16 bg-gradient-to-r from-transparent via-blue-400 to-transparent"></div>
          <div class="w-2 h-2 rounded-full bg-blue-400"></div>
          <div class="h-px w-16 bg-gradient-to-r from-transparent via-purple-400 to-transparent"></div>
        </div>

        <!-- Navigation buttons -->
        <div class="flex flex-col sm:flex-row gap-4 justify-center items-center">
          <a
            :href="homeLink"
            class="group relative px-8 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-full font-medium transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/50 hover:scale-105 transform"
          >
            <span v-if="isChinese">返回首页</span>
            <span v-else>Return Home</span>
            <svg
              class="inline-block ml-2 w-5 h-5 transform transition-transform group-hover:translate-x-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13 7l5 5m0 0l-5 5m5-5H6"
              />
            </svg>
          </a>

          <button
            @click="goBack"
            class="px-8 py-3 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-full font-medium transition-all duration-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:border-gray-400 dark:hover:border-gray-500"
          >
            <span v-if="isChinese">返回上页</span>
            <span v-else>Go Back</span>
          </button>
        </div>

        <!-- Additional philosophical note -->
        <div class="mt-12 pt-8 border-t border-gray-200 dark:border-gray-700">
          <p class="text-sm text-gray-400 dark:text-gray-500 italic">
            <span v-if="isChinese">
              正如庄子所言："道不可闻，闻而非也；道不可见，见而非也。"
            </span>
            <span v-else>
              As Lao Tzu said: "The way that can be spoken is not the eternal way."
            </span>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useData } from 'vitepress'

let path = ref('')
let localePath = ref('')
try {
  const data = useData()
  if (data) {
    path = data.path || ref('')
    localePath = data.localePath || ref('')
  }
} catch (e) {
  // Fallback if useData fails
}

const isChinese = computed(() => {
  // Check window.location first (most reliable in browser)
  if (typeof window !== 'undefined') {
    const windowPath = window.location.pathname
    if (windowPath.startsWith('/zh')) {
      return true
    }
    if (windowPath.startsWith('/en')) {
      return false
    }
  }

  // Fallback to path from useData
  try {
    if (!path || typeof path !== 'object' || path === null) {
      return true
    }
    const currentPath = (typeof path.value !== 'undefined') ? path.value : ''
    if (currentPath && typeof currentPath === 'string') {
      if (currentPath.startsWith('/zh')) {
        return true
      }
      if (currentPath.startsWith('/en')) {
        return false
      }
    }
  } catch (e) {
    // Ignore errors
  }

  // Default to Chinese for root locale
  return true
})

const homeLink = computed(() => {
  return isChinese.value ? '/zh/' : '/en/'
})

const goBack = () => {
  if (typeof window !== 'undefined') {
    window.history.back()
  }
}

const particlePositions = ref([])

onMounted(() => {
  const positions = []
  for (let i = 0; i < 12; i++) {
    const size = 20 + Math.random() * 40
    const left = Math.random() * 100
    const top = Math.random() * 100
    const delay = Math.random() * 5
    const duration = 10 + Math.random() * 10
    const color1 = Math.floor(99 + Math.random() * 100)
    const color2 = Math.floor(102 + Math.random() * 100)
    const color3 = Math.floor(141 + Math.random() * 100)

    positions.push({
      width: `${size}px`,
      height: `${size}px`,
      left: `${left}%`,
      top: `${top}%`,
      background: `radial-gradient(circle,
        rgba(${color1}, ${color2}, ${color3}, 0.3),
        rgba(${color1}, ${color2}, ${color3}, 0)
      )`,
      '--delay': `${delay}s`,
      '--duration': `${duration}s`,
    })
  }
  particlePositions.value = positions
})
</script>

<style scoped>
.not-found-wrapper {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* Smooth fade in */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.not-found-wrapper > div {
  animation: fadeIn 0.8s ease-out;
}

.particle {
  animation: float var(--duration, 15s) ease-in-out var(--delay, 0s) infinite alternate;
}

@keyframes float {
  0% {
    transform: translateY(0) translateX(0) rotate(0deg);
    opacity: 0.2;
  }
  50% {
    opacity: 0.4;
  }
  100% {
    transform: translateY(-30px) translateX(20px) rotate(180deg);
    opacity: 0.1;
  }
}
</style>
