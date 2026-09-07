<template>
  <footer class="footer-wrapper relative text-gray-300 py-8 md:py-10 overflow-hidden">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-6">
        <!-- Company Info -->
        <div>
          <h3 class="text-white font-semibold text-lg mb-3">{{ companyName }}</h3>
          <p class="text-sm text-gray-400 mb-3">
            {{ companyDescription }}
          </p>
          <!-- Social Links -->
          <div class="flex gap-4" v-if="socialLinks && socialLinks.length > 0">
            <a
              v-for="(link, index) in socialLinks"
              :key="index"
              :href="link.url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-gray-400 hover:text-white transition-colors duration-200"
              :aria-label="link.name"
            >
              <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path v-if="link.icon === 'github'" d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                <path v-else-if="link.icon === 'twitter'" d="M23 3a10.9 10.9 0 01-3.14 1.53 4.48 4.48 0 00-7.86 3v1A10.66 10.66 0 013 4s-4 9 5 13a11.64 11.64 0 01-7 2c9 5 20 0 20-11.5a4.5 4.5 0 00-.08-.83A7.72 7.72 0 0023 3z"/>
                <circle v-else cx="12" cy="12" r="10"/>
              </svg>
            </a>
          </div>
        </div>

        <!-- Product Links -->
        <div v-if="productLinks && productLinks.length > 0">
          <h4 class="text-white font-semibold mb-3">{{ productTitle }}</h4>
          <ul class="space-y-1.5">
            <li v-for="(link, index) in productLinks" :key="index">
              <a
                :href="link.url"
                class="text-sm hover:text-white transition-colors duration-200 inline-flex items-center py-0.5"
              >
                {{ link.text }}
              </a>
            </li>
          </ul>
        </div>

        <!-- Resources Links -->
        <div v-if="resourceLinks && resourceLinks.length > 0">
          <h4 class="text-white font-semibold mb-3">{{ resourceTitle }}</h4>
          <ul class="space-y-1.5">
            <li v-for="(link, index) in resourceLinks" :key="index">
              <a
                :href="link.url"
                class="text-sm hover:text-white transition-colors duration-200 inline-flex items-center py-0.5"
              >
                {{ link.text }}
              </a>
            </li>
          </ul>
        </div>

        <!-- Company Links -->
        <div v-if="companyLinks && companyLinks.length > 0">
          <h4 class="text-white font-semibold mb-3">{{ companyTitle }}</h4>
          <ul class="space-y-1.5">
            <li v-for="(link, index) in companyLinks" :key="index">
              <a
                v-if="link.mailto"
                href="#"
                class="text-sm hover:text-white transition-colors duration-200 inline-flex items-center py-0.5"
                @click.prevent="openMail(link.mailto)"
              >
                {{ link.text }}
              </a>
              <a
                v-else
                :href="link.url"
                class="text-sm hover:text-white transition-colors duration-200 inline-flex items-center py-0.5"
              >
                {{ link.text }}
              </a>
            </li>
          </ul>
        </div>

        <!-- About Links -->
        <div v-if="aboutLinks && aboutLinks.length > 0">
          <h4 class="text-white font-semibold mb-3">{{ aboutTitle }}</h4>
          <ul class="space-y-1.5">
            <li v-for="(link, index) in aboutLinks" :key="index">
              <a
                :href="link.url"
                class="text-sm hover:text-white transition-colors duration-200 inline-flex items-center py-0.5"
              >
                {{ link.text }}
              </a>
            </li>
          </ul>
        </div>
      </div>

      <!-- Bottom Bar -->
      <div class="pt-6 mt-6 border-t border-gray-700">
        <div class="flex flex-col md:flex-row justify-between items-center gap-4">
          <p class="text-sm text-gray-400">
            © {{ new Date().getFullYear() }} {{ companyName }}
          </p>
          <div v-if="legalLinks && legalLinks.length > 0" class="flex gap-6">
            <a
              v-for="(link, index) in legalLinks"
              :key="index"
              :href="link.url"
              class="text-sm text-gray-400 hover:text-white transition-colors duration-200"
            >
              {{ link.text }}
            </a>
          </div>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { openMail } from '../utils/mailto.js'

defineProps({
  companyName: {
    type: String,
    default: 'Devify'
  },
  companyDescription: {
    type: String,
    default: 'AI-Powered Conversation Management Platform'
  },
  copyright: {
    type: String,
    default: '© 2024 Devify. All rights reserved.'
  },
  productTitle: {
    type: String,
    default: 'Product'
  },
  resourceTitle: {
    type: String,
    default: 'Resources'
  },
  companyTitle: {
    type: String,
    default: 'Company'
  },
  aboutTitle: {
    type: String,
    default: 'About'
  },
  socialLinks: {
    type: Array,
    default: () => []
  },
  productLinks: {
    type: Array,
    default: () => []
  },
  resourceLinks: {
    type: Array,
    default: () => []
  },
  companyLinks: {
    type: Array,
    default: () => []
  },
  aboutLinks: {
    type: Array,
    default: () => []
  },
  legalLinks: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.footer-wrapper {
  background: #0f172a;
  position: relative;
}

.footer-wrapper::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.2) 0%, transparent 40%),
    radial-gradient(circle at 80% 70%, rgba(168, 85, 247, 0.15) 0%, transparent 40%);
  z-index: 0;
}

.footer-wrapper::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.5), transparent);
}
</style>
