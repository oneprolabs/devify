<template>
  <div class="comparison-wrapper py-12 md:py-16 bg-gradient-to-b from-white to-gray-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Divider -->
      <div class="flex items-center mb-12">
        <div class="flex-grow border-t border-gray-300"></div>
        <div class="mx-4">
          <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <div class="flex-grow border-t border-gray-300"></div>
      </div>

      <!-- Section Header -->
      <div class="text-center mb-8">
        <h3 class="text-2xl md:text-3xl font-bold text-gray-900 mb-2">
          {{ title }}
        </h3>
        <p class="text-gray-600">
          {{ subtitle }}
        </p>
      </div>

      <!-- Mobile: Swipeable table -->
      <div class="overflow-x-auto -mx-4 sm:mx-0 rounded-xl border border-gray-200 shadow-sm bg-white">
        <div class="inline-block min-w-full align-middle px-4 sm:px-0">
          <table class="min-w-full border-collapse">
            <thead>
              <tr class="border-b-2 border-gray-200">
                <th class="sticky left-0 z-10 bg-white px-4 py-4 text-left text-sm font-semibold text-gray-900 min-w-[140px]">
                  {{ featureColumnTitle }}
                </th>
                <th
                  v-for="(plan, index) in plans"
                  :key="index"
                  :class="[
                    'px-4 py-4 text-center text-sm font-semibold min-w-[120px]',
                    plan.featured ? 'bg-primary-50 text-primary-900' : 'text-gray-900'
                  ]"
                >
                  <div class="flex flex-col items-center gap-1">
                    <span>{{ plan.name }}</span>
                    <span class="text-xs font-normal text-gray-600">{{ plan.price }}</span>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(feature, fIndex) in comparisonFeatures"
                :key="fIndex"
                :class="[
                  'border-b border-gray-100',
                  feature.highlighted ? 'bg-blue-50' : fIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'
                ]"
              >
                <td class="sticky left-0 z-10 px-4 py-3 text-sm text-gray-900 font-medium"
                    :class="fIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'"
                >
                  {{ feature.name }}
                </td>
                <td
                  v-for="(plan, pIndex) in plans"
                  :key="pIndex"
                  :class="[
                    'px-4 py-3 text-center text-sm',
                    plan.featured ? 'bg-primary-50' : ''
                  ]"
                >
                  <span v-if="typeof feature.values[pIndex] === 'boolean'">
                    <svg v-if="feature.values[pIndex]" class="w-5 h-5 text-green-500 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                    <svg v-else class="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                  </span>
                  <span v-else :class="[
                    feature.highlighted ? 'font-semibold' : '',
                    feature.values[pIndex] === '不支持' || feature.values[pIndex] === '基础版' || feature.values[pIndex] === '基础搜索'
                      ? 'text-gray-500'
                      : feature.values[pIndex] === '完整版' || feature.values[pIndex] === '高级搜索' || feature.values[pIndex] === '支持' || feature.values[pIndex] === '永久'
                        ? 'text-primary-700 font-medium'
                        : 'text-gray-700'
                  ]">
                    {{ feature.values[pIndex] }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Mobile hint -->
      <div class="sm:hidden mt-4 text-center">
        <p class="text-xs text-gray-500">
          {{ swipeHint }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: 'Detailed Plan Comparison'
  },
  subtitle: {
    type: String,
    default: 'Compare all features across plans'
  },
  featureColumnTitle: {
    type: String,
    default: 'Features'
  },
  swipeHint: {
    type: String,
    default: '← Swipe to view more →'
  },
  plans: {
    type: Array,
    required: true
  },
  comparisonFeatures: {
    type: Array,
    required: true
  }
})
</script>

<style scoped>
.comparison-wrapper {
  position: relative;
}

table {
  border-spacing: 0;
}

th {
  position: sticky;
  top: 0;
  background: white;
}

.sticky {
  position: sticky;
}

@media (max-width: 640px) {
  table {
    font-size: 0.813rem;
  }

  th, td {
    padding: 0.5rem !important;
  }

  th .flex {
    gap: 0.25rem !important;
  }
}

.overflow-x-auto {
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
}

.overflow-x-auto::-webkit-scrollbar {
  height: 8px;
}

.overflow-x-auto::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}

.overflow-x-auto::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.overflow-x-auto::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
