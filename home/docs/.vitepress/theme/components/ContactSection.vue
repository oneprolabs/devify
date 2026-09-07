<template>
  <div class="contact-wrapper">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="contact-header">
        <h2 class="contact-title">{{ title }}</h2>
        <p class="contact-subtitle">{{ subtitle }}</p>
      </div>

      <div class="contact-grid">
        <a
          v-for="(item, index) in items"
          :key="index"
          href="#"
          class="contact-card"
          @click.prevent="openMail(item)"
        >
          <div class="contact-icon">
            <svg v-if="item.icon === 'deploy'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="6" rx="1.5" />
              <rect x="3" y="14" width="18" height="6" rx="1.5" />
              <circle cx="7" cy="7" r="0.6" fill="currentColor" stroke="none" />
              <circle cx="7" cy="17" r="0.6" fill="currentColor" stroke="none" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="3.5" />
              <line x1="12" y1="3" x2="12" y2="8.5" />
              <line x1="12" y1="15.5" x2="12" y2="21" />
              <line x1="3" y1="12" x2="8.5" y2="12" />
              <line x1="15.5" y1="12" x2="21" y2="12" />
            </svg>
          </div>
          <h3 class="contact-card-title">{{ item.title }}</h3>
          <p class="contact-card-desc">{{ item.description }}</p>
          <span class="contact-email">
            {{ ctaLabel }}
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </span>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { openMail } from '../utils/mailto.js'

defineProps({
  title: {
    type: String,
    default: 'Get in touch'
  },
  subtitle: {
    type: String,
    default: ''
  },
  ctaLabel: {
    type: String,
    default: 'Email us'
  },
  items: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.contact-wrapper {
  padding: 3.5rem 0;
  background: #0f172a;
}

.contact-header {
  text-align: center;
  margin-bottom: 2.5rem;
}

.contact-title {
  font-size: 1.75rem;
  font-weight: 800;
  color: white;
  margin-bottom: 0.6rem;
}

@media (min-width: 768px) {
  .contact-title {
    font-size: 2rem;
  }
}

.contact-subtitle {
  color: #94a3b8;
  font-size: 1rem;
}

.contact-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.25rem;
}

@media (min-width: 640px) {
  .contact-grid {
    grid-template-columns: 1fr 1fr;
  }
}

.contact-card {
  display: block;
  padding: 1.75rem;
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  text-decoration: none;
  transition: all 0.2s;
}

.contact-card:hover {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.35);
  transform: translateY(-2px);
}

.contact-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 0.65rem;
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  margin-bottom: 1rem;
}

.contact-icon svg {
  width: 1.4rem;
  height: 1.4rem;
}

.contact-card-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: white;
  margin-bottom: 0.4rem;
}

.contact-card-desc {
  font-size: 0.9rem;
  color: #94a3b8;
  line-height: 1.6;
  margin-bottom: 1.1rem;
}

.contact-email {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: #a5b4fc;
}

.contact-card:hover .contact-email {
  color: #c7d2fe;
}
</style>
