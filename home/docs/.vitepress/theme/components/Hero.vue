<template>
  <div class="hero-wrapper relative overflow-hidden">
    <!-- Mesh gradient background -->
    <div class="hero-bg"></div>
    <div class="hero-glow hero-glow-1"></div>
    <div class="hero-glow hero-glow-2"></div>
    <div class="hero-glow hero-glow-3"></div>
    <!-- Grid overlay -->
    <div class="hero-grid"></div>

    <div class="hero-container relative z-10 py-16 md:py-24 lg:py-32">
      <div class="hero-stack px-4 sm:px-6 lg:px-8 flex flex-col items-center">

        <!-- Badges -->
        <div class="flex flex-wrap justify-center gap-2 mb-6" v-if="badge || githubUrl">
          <span v-if="badge" class="hero-badge">
            {{ badge }}
          </span>
          <a v-if="githubUrl" :href="githubUrl" target="_blank" rel="noopener" class="hero-github-badge">
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
            </svg>
            ⭐ Open Source
          </a>
        </div>

        <!-- Title -->
        <h1 class="hero-title" v-html="formattedTitle"></h1>

        <!-- Subtitle -->
        <p v-if="heroSubtitle" class="hero-subtitle">{{ heroSubtitle }}</p>

        <!-- CTA Buttons -->
        <div class="flex flex-col sm:flex-row gap-3 mb-10">
          <a :href="primaryButtonLink"
             class="cta-primary">
            {{ primaryButtonText }}
            <svg class="ml-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </a>
          <a :href="secondaryButtonLink" class="cta-secondary">
            {{ secondaryButtonText }}
          </a>
        </div>

        <!-- Carousel / Screenshot -->
        <div class="hero-visual w-full">
          <div v-if="carouselSlides && carouselSlides.length > 0" class="carousel-shadow-wrap">
            <Carousel :slides="carouselSlides" :autoplay="true" :interval="5000" :overlay-points="points" />
          </div>
          <div v-else-if="imageSrc" class="carousel-shadow-wrap">
            <img :src="imageSrc" :alt="imageAlt" class="w-full h-auto rounded-xl" loading="lazy" />
          </div>
        </div>

      </div>
    </div>

  </div>
</template>

<script setup>
import { computed } from 'vue'
import Carousel from './Carousel.vue'

const props = defineProps({
  badge: { type: String, default: '' },
  githubUrl: { type: String, default: '' },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  points: { type: Array, default: () => [] },
  primaryButtonText: { type: String, default: 'Get Started' },
  primaryButtonLink: { type: String, default: '#' },
  secondaryButtonText: { type: String, default: 'Learn More' },
  secondaryButtonLink: { type: String, default: '#' },
  imageSrc: { type: String, default: '' },
  imageAlt: { type: String, default: 'Product screenshot' },
  features: { type: Array, default: () => [] },
  carouselSlides: { type: Array, default: () => [] },
})

const formattedTitle = computed(() => props.title || '')
const heroSubtitle = computed(() => (props.subtitle || '').trim())
</script>

<style scoped>
/* ── Base ── */
.hero-wrapper {
  background: #ffffff;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Mesh gradient (light aura) ── */
.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 90% 70% at 50% -10%, rgba(99, 102, 241, 0.1) 0%, transparent 65%),
    radial-gradient(ellipse 60% 50% at 85% 40%, rgba(139, 92, 246, 0.07) 0%, transparent 55%),
    radial-gradient(ellipse 50% 50% at 10% 75%, rgba(59, 130, 246, 0.06) 0%, transparent 55%);
}

.hero-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  animation: float 20s ease-in-out infinite;
}
.hero-glow-1 {
  width: 700px; height: 700px;
  top: -30%; right: -10%;
  background: rgba(99, 102, 241, 0.1);
  animation-delay: 0s;
}
.hero-glow-2 {
  width: 500px; height: 500px;
  bottom: -5%; left: -5%;
  background: rgba(139, 92, 246, 0.08);
  animation-delay: 7s;
}
.hero-glow-3 {
  width: 400px; height: 400px;
  top: 35%; left: 40%;
  background: rgba(99, 102, 241, 0.06);
  animation-delay: 14s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33%       { transform: translate(25px, -20px) scale(1.04); }
  66%       { transform: translate(-18px, 18px) scale(0.96); }
}

/* ── Grid overlay ── */
.hero-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(99,102,241,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(99,102,241,0.04) 1px, transparent 1px);
  background-size: 60px 60px;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, black 20%, transparent 100%);
}

/* ── Container ── */
.hero-container { position: relative; z-index: 10; }

.hero-stack {
  max-width: 1180px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

/* ── Badges ── */
.hero-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 500;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.22);
  color: #4f46e5;
  letter-spacing: 0.03em;
}

.hero-github-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 500;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #374151;
  text-decoration: none;
  transition: all 0.2s;
}
.hero-github-badge:hover {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #4f46e5;
}

/* ── Title ── */
.hero-title {
  font-size: clamp(2.4rem, 6vw, 4.25rem);
  font-weight: 900;
  line-height: 1.1;
  text-align: center;
  color: #0f172a;
  letter-spacing: -0.02em;
  margin: 0 0 1.25rem;
  max-width: 860px;
  word-break: keep-all;
}

/* ── Subtitle ── */
.hero-subtitle {
  font-size: clamp(1rem, 2vw, 1.2rem);
  color: #475569;
  line-height: 1.65;
  text-align: center;
  max-width: 680px;
  margin: 0 0 2rem;
}

/* ── CTAs ── */
.cta-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.85rem 2rem;
  border-radius: 0.6rem;
  font-weight: 700;
  font-size: 1rem;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  text-decoration: none;
  box-shadow: 0 4px 14px rgba(99,102,241,0.35), 0 1px 3px rgba(99,102,241,0.2);
  transition: all 0.2s;
}
.cta-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(99,102,241,0.45), 0 2px 6px rgba(99,102,241,0.25);
}

.cta-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.85rem 2rem;
  border-radius: 0.6rem;
  font-weight: 600;
  font-size: 1rem;
  background: transparent;
  color: #374151;
  border: 1px solid #d1d5db;
  text-decoration: none;
  transition: all 0.2s;
}
.cta-secondary:hover {
  background: #eef2ff;
  border-color: #818cf8;
  color: #4f46e5;
}

/* ── Visual ── */
.hero-visual {
  max-width: 1100px;
  width: 100%;
}

.carousel-shadow-wrap {
  border-radius: 1rem;
  overflow: hidden;
  box-shadow:
    0 0 0 1px rgba(0,0,0,0.06),
    0 24px 60px -12px rgba(99,102,241,0.2),
    0 8px 24px rgba(0,0,0,0.08);
}

/* ── Mobile ── */
@media (max-width: 640px) {
  .hero-wrapper { min-height: auto; }
  .hero-title { font-size: 2rem; line-height: 1.15; }
  .hero-subtitle { font-size: 0.95rem; }
  .cta-primary, .cta-secondary { width: 100%; }
  .hero-glow-1 { width: 300px; height: 300px; }
  .hero-glow-2 { width: 250px; height: 250px; }
}
</style>
