<template>
  <div id="pricing" class="pricing-wrapper relative py-16 md:py-24 overflow-hidden">
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

      <!-- Pricing Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8">
        <div
          v-for="(plan, index) in plans"
          :key="index"
          :class="[
            'pricing-card flex flex-col',
            plan.featured ? 'featured ring-2 ring-primary-600' : 'bg-white'
          ]"
        >
          <!-- Featured Badge -->
          <div v-if="plan.featured" class="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
            <span class="inline-flex items-center px-4 py-1 rounded-full text-xs font-semibold bg-primary-600 text-white shadow-lg">
              {{ featuredLabel }}
            </span>
          </div>

          <!-- Plan Name -->
          <h3 class="text-xl font-semibold text-gray-900 mb-2">
            {{ plan.name }}
          </h3>

          <!-- Plan Description -->
          <p class="text-sm text-gray-600 mb-6 min-h-[2.5rem]">
            {{ plan.description }}
          </p>

          <!-- Price -->
          <div class="mb-6">
            <div class="flex items-baseline">
              <span class="text-4xl font-bold text-gray-900">
                {{ plan.price }}
              </span>
              <span class="text-gray-600 ml-2">
                {{ plan.period }}
              </span>
            </div>
          </div>

          <!-- CTA Button -->
          <a
            :href="plan.buttonLink"
            :class="[
              'block w-full text-center px-6 py-3 rounded-lg font-medium transition-all duration-200 mb-6 min-h-[44px] flex items-center justify-center',
              plan.featured
                ? 'bg-primary-600 text-white hover:bg-primary-700 shadow-lg hover:shadow-xl'
                : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
            ]"
          >
            {{ plan.buttonText }}
          </a>

          <!-- Features List -->
          <ul class="space-y-3 flex-grow">
            <li
              v-for="(feature, fIndex) in plan.features"
              :key="fIndex"
              class="flex items-start"
            >
              <span class="text-sm text-gray-700" v-html="feature"></span>
            </li>
          </ul>

          <!-- Additional Info (always rendered for alignment) -->
          <div class="mt-6 pt-6 border-t border-gray-200">
            <p class="text-xs text-gray-500 min-h-[2.5rem] flex items-center">
              {{ plan.additionalInfo || '\u00A0' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Private deployment CTA — parallel to the fixed-price tiers above -->
      <div v-if="contactCta" class="contact-cta-strip">
        <div class="contact-cta-text">
          <h3 class="contact-cta-title">{{ contactCta.title }}</h3>
          <p class="contact-cta-desc">{{ contactCta.description }}</p>
        </div>
        <a href="#" class="contact-cta-button" @click.prevent="openMail(contactCta.mailto)">
          {{ contactCta.buttonText }}
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
          </svg>
        </a>
      </div>

      <!-- FAQ or Additional Info -->
      <div v-if="note" class="mt-8 text-center">
        <p class="text-gray-600">
          {{ note }}
        </p>
      </div>

      <!-- Hint for detailed comparison below -->
      <div v-if="comparisonHint" class="mt-8 text-center">
        <p class="text-sm text-gray-500 animate-bounce">
          {{ comparisonHint }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { openMail } from '../utils/mailto.js'

defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  },
  featuredLabel: {
    type: String,
    default: 'Popular'
  },
  plans: {
    type: Array,
    required: true
  },
  note: {
    type: String,
    default: ''
  },
  comparisonHint: {
    type: String,
    default: ''
  },
  contactCta: {
    type: Object,
    default: null
  }
})

const isBasicFeature = (feature) => {
  if (typeof feature !== 'string') return false
  return feature.includes('基础') || feature.includes('不支持')
}

const isExclusiveFeature = (feature) => {
  if (typeof feature !== 'string') return false
  // 独有功能：只在高级方案中才有的功能
  const exclusiveKeywords = [
    '永久保存',
    'IMAP',
    'JIRA'
  ]
  return exclusiveKeywords.some(keyword => feature.includes(keyword))
}

const isFeaturedFeature = (feature) => {
  if (typeof feature !== 'string') return false
  // 如果已经是独有功能，就不再标记为特色功能
  if (isExclusiveFeature(feature)) return false
  const featuredKeywords = [
    '高级',
    '多场景',
    '元数据',
    '非图片附件',
    '多语言',
    '专属'
  ]
  return featuredKeywords.some(keyword => feature.includes(keyword))
}
</script>

<style scoped>
.pricing-wrapper {
  background: #f8fafc;
}

.pricing-wrapper::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.03) 0%, transparent 50%),
    radial-gradient(circle at 90% 80%, rgba(168, 85, 247, 0.03) 0%, transparent 50%);
  z-index: 0;
}

.pricing-card {
  @apply relative rounded-xl p-8 shadow-lg transition-all duration-300;
  background: white;
  border: 2px solid transparent;
}

.pricing-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 0.75rem;
  padding: 2px;
  background: linear-gradient(135deg, #667eea, #764ba2, #f093fb);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.pricing-card:hover::before {
  opacity: 1;
}

.pricing-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 25px 50px -12px rgba(99, 102, 241, 0.25);
}

.pricing-card.featured {
  transform: scale(1.05);
  border-color: #6366f1;
  background: linear-gradient(to bottom, #ffffff 0%, #faf5ff 100%);
}

.pricing-card.featured::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.1));
  z-index: -1;
}

.pricing-card.featured:hover {
  transform: scale(1.05) translateY(-8px);
  box-shadow: 0 30px 60px -15px rgba(99, 102, 241, 0.35);
}

@media (max-width: 1024px) {
  .pricing-card.featured {
    transform: scale(1);
  }

  .pricing-card.featured:hover {
    transform: translateY(-8px);
  }
}

@media (max-width: 640px) {
  .pricing-card {
    @apply p-6;
  }
}

/* Private-deployment CTA strip — sits parallel to the fixed-price tiers */
.contact-cta-strip {
  position: relative;
  z-index: 1;
  margin-top: 2.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  align-items: center;
  justify-content: space-between;
  padding: 1.75rem 2rem;
  border-radius: 1rem;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(139, 92, 246, 0.05));
  border: 1px solid rgba(99, 102, 241, 0.16);
  text-align: center;
}

@media (min-width: 768px) {
  .contact-cta-strip {
    flex-direction: row;
    text-align: left;
    padding: 1.75rem 2.5rem;
  }
}

.contact-cta-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #1e1b4b;
  margin-bottom: 0.3rem;
}

.contact-cta-desc {
  font-size: 0.9rem;
  color: #64748b;
  line-height: 1.6;
}

.contact-cta-button {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.5rem;
  border-radius: 0.6rem;
  font-weight: 600;
  font-size: 0.9rem;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  text-decoration: none;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
  transition: all 0.2s;
  white-space: nowrap;
}

.contact-cta-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.4);
}
</style>
