<template>
  <div class="carousel-wrapper relative">
    <!-- Carousel Container -->
    <div class="carousel-container relative overflow-hidden rounded-xl shadow-2xl border border-gray-200 bg-white">
      <!-- Slides -->
      <div
        class="carousel-slides"
        :style="{ transform: `translateX(-${currentIndex * 100}%)` }"
      >
        <div
          v-for="(slide, index) in slides"
          :key="index"
          class="carousel-slide"
        >
          <img
            :src="slide.image"
            :alt="slide.alt"
            class="w-full h-auto"
            loading="lazy"
            role="button"
            tabindex="0"
            @click="openLightbox(slide)"
            @keyup.enter="openLightbox(slide)"
          />
          <div v-if="slide.title || slide.description" class="carousel-caption">
            <h3 v-if="slide.title" class="carousel-title">{{ slide.title }}</h3>
            <p v-if="slide.description" class="carousel-description">{{ slide.description }}</p>
          </div>
        </div>
      </div>

      <!-- Navigation Arrows -->
      <button
        v-if="slides.length > 1"
        @click="previousSlide"
        class="carousel-nav carousel-nav-prev"
        aria-label="Previous slide"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
      <button
        v-if="slides.length > 1"
        @click="nextSlide"
        class="carousel-nav carousel-nav-next"
        aria-label="Next slide"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>

    </div>
    <Teleport to="body">
      <Transition name="lightbox-fade">
        <div
          v-if="isLightboxOpen && activeSlide"
          class="lightbox-overlay"
          @click="closeLightbox"
        >
          <div class="lightbox-content" @click.stop>
            <button
              type="button"
              class="lightbox-close"
              @click="closeLightbox"
              aria-label="Close image preview"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <img
              class="lightbox-image"
              :src="activeSlide.image"
              :alt="activeSlide.alt"
            />
            <div v-if="activeSlide.title || activeSlide.description" class="lightbox-caption">
              <h3 v-if="activeSlide.title" class="lightbox-title">{{ activeSlide.title }}</h3>
              <p v-if="activeSlide.description" class="lightbox-description">{{ activeSlide.description }}</p>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  slides: {
    type: Array,
    required: true,
    default: () => [],
    validator: (slides) => {
      if (!Array.isArray(slides) || slides.length === 0) {
        return true
      }
      return slides.every(slide => slide && slide.image && slide.alt)
    }
  },
  autoplay: {
    type: Boolean,
    default: true
  },
  interval: {
    type: Number,
    default: 5000 // 5 seconds
  },
  loop: {
    type: Boolean,
    default: true
  },
  overlayPoints: {
    type: Array,
    default: () => []
  }
})

const currentIndex = ref(0)
const isLightboxOpen = ref(false)
const activeSlide = ref(null)
let autoplayTimer = null
const nextSlide = () => {
  if (!props.slides || props.slides.length === 0) return
  if (props.loop) {
    currentIndex.value = (currentIndex.value + 1) % props.slides.length
  } else {
    currentIndex.value = Math.min(currentIndex.value + 1, props.slides.length - 1)
  }
  resetAutoplay()
}

const previousSlide = () => {
  if (!props.slides || props.slides.length === 0) return
  if (props.loop) {
    currentIndex.value = (currentIndex.value - 1 + props.slides.length) % props.slides.length
  } else {
    currentIndex.value = Math.max(currentIndex.value - 1, 0)
  }
  resetAutoplay()
}

const goToSlide = (index) => {
  currentIndex.value = index
  resetAutoplay()
}

const resetAutoplay = () => {
  if (autoplayTimer) {
    clearInterval(autoplayTimer)
  }
  if (props.autoplay && props.slides.length > 1) {
    autoplayTimer = setInterval(() => {
      nextSlide()
    }, props.interval)
  }
}

const openLightbox = (slide) => {
  if (!slide) {
    return
  }
  activeSlide.value = slide
  isLightboxOpen.value = true
}

const closeLightbox = () => {
  isLightboxOpen.value = false
  activeSlide.value = null
}

const handleKeydown = (event) => {
  if (event.key === 'Escape' && isLightboxOpen.value) {
    closeLightbox()
  }
}

const resolveText = (point) => {
  if (!point) {
    return ''
  }
  return typeof point === 'string' ? point : point.text || ''
}

const getHighlights = (slide) => {
  if (slide && Array.isArray(slide.highlights) && slide.highlights.length > 0) {
    return slide.highlights
  }
  if (Array.isArray(props.overlayPoints) && props.overlayPoints.length > 0) {
    return props.overlayPoints
  }
  return []
}

const toggleBodyScroll = (locked) => {
  if (typeof document === 'undefined') {
    return
  }
  document.body.classList.toggle('lightbox-locked', locked)
}

watch(isLightboxOpen, (open) => {
  toggleBodyScroll(open)
})

onMounted(() => {
  if (props.autoplay && props.slides.length > 1) {
    resetAutoplay()
  }
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  if (autoplayTimer) {
    clearInterval(autoplayTimer)
  }
  window.removeEventListener('keydown', handleKeydown)
  toggleBodyScroll(false)
})
</script>

<style scoped>
.carousel-wrapper {
  width: 100%;
}

.carousel-container {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 10;
  max-height: 550px;
}

.carousel-slides {
  display: flex;
  transition: transform 0.5s ease-in-out;
  height: 100%;
}

.carousel-slide {
  min-width: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
}

.carousel-slide img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #f9fafb;
  cursor: zoom-in;
}

.carousel-caption {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 1.25rem 1.5rem;
  color: #0f172a;
  background: linear-gradient(
    to top,
    rgba(248, 250, 252, 0.96),
    rgba(248, 250, 252, 0.6),
    transparent
  );
  backdrop-filter: blur(6px);
  border-top: 1px solid rgba(148, 163, 184, 0.35);
  box-shadow: 0 -6px 12px rgba(15, 23, 42, 0.08);
}

.carousel-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #0f172a;
}

.carousel-description {
  font-size: 0.95rem;
  line-height: 1.45;
  color: #334155;
}

.caption-highlights {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.75rem;
}

.caption-highlight {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  color: #1e293b;
  font-size: 0.9rem;
  line-height: 1.4;
}

.caption-bullet {
  width: 8px;
  height: 8px;
  margin-top: 0.5rem;
  border-radius: 9999px;
  background: #2563eb;
  flex-shrink: 0;
}

.caption-text {
  flex: 1;
}

.carousel-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 10;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #374151;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.carousel-nav:hover {
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  transform: translateY(-50%) scale(1.1);
}

.carousel-nav-prev {
  left: 1rem;
}

.carousel-nav-next {
  right: 1rem;
}

.carousel-indicators {
  position: absolute;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 0.5rem;
  z-index: 10;
}

.carousel-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.5);
  border: 2px solid rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: all 0.3s ease;
  padding: 0;
}

.carousel-indicator:hover {
  background: rgba(255, 255, 255, 0.8);
  transform: scale(1.2);
}

.carousel-indicator.active {
  background: white;
  width: 24px;
  border-radius: 5px;
}

.lightbox-overlay {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  z-index: 50;
}

.lightbox-content {
  position: relative;
  max-width: min(1200px, 95vw);
  max-height: 90vh;
  background: radial-gradient(circle at top, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95));
  border-radius: 1rem;
  overflow: hidden;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transform-origin: center;
}

.lightbox-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #020617;
}

.lightbox-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 40px;
  height: 40px;
  border-radius: 9999px;
  background: rgba(15, 23, 42, 0.8);
  color: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(226, 232, 240, 0.2);
  cursor: pointer;
  transition: all 0.2s ease;
}

.lightbox-close:hover {
  background: rgba(15, 23, 42, 1);
  transform: scale(1.05);
}

.lightbox-caption {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 1.25rem 1.5rem;
  background: linear-gradient(0deg, rgba(2, 6, 23, 0.98), rgba(2, 6, 23, 0.65), transparent);
  color: #e2e8f0;
}

.lightbox-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.lightbox-description {
  font-size: 0.95rem;
  color: #cbd5f5;
}

/* Mobile adjustments */
@media (max-width: 640px) {
  .carousel-container {
    aspect-ratio: 4 / 3;
    max-height: 400px;
  }

  .carousel-nav {
    width: 40px;
    height: 40px;
  }

  .carousel-nav-prev {
    left: 0.5rem;
  }

  .carousel-nav-next {
    right: 0.5rem;
  }

  .carousel-caption {
    padding: 1rem;
  }

  .carousel-title {
    font-size: 1.05rem;
  }

  .carousel-description {
    font-size: 0.85rem;
    display: none;
  }

  .lightbox-content {
    max-height: 80vh;
    padding-bottom: 3rem;
  }

  .lightbox-caption {
    padding: 1rem;
  }

  .lightbox-title {
    font-size: 1.1rem;
  }

  .lightbox-description {
    font-size: 0.85rem;
  }
}

:global(body.lightbox-locked) {
  overflow: hidden;
}

.lightbox-fade-enter-active,
.lightbox-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.lightbox-fade-enter-from,
.lightbox-fade-leave-to {
  opacity: 0;
}

:global(.lightbox-fade-enter-from .lightbox-content),
:global(.lightbox-fade-leave-to .lightbox-content) {
  transform: scale(0.96);
  opacity: 0.8;
}
</style>
