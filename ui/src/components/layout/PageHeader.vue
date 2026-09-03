<template>
  <header
    class="flex h-[52px] flex-shrink-0 items-center gap-3 border-b border-line bg-app md:h-[56px]"
    :class="paddingClass"
  >
    <div class="flex items-baseline gap-2 min-w-0">
      <!-- Where this page sits, for the ones nested under an app. -->
      <template v-if="parent">
        <router-link
          :to="parent.to"
          class="hidden flex-none text-[12.5px] text-ink-3 transition-colors hover:text-ink md:block"
        >
          {{ parent.label }}
        </router-link>
        <span class="hidden flex-none text-[12.5px] text-ink-4 md:block">
          /
        </span>
      </template>
      <h1 class="truncate text-base font-semibold text-ink md:text-[14.5px]">
        {{ title }}
      </h1>
      <span v-if="count !== null" class="font-mono text-[11px] text-ink-3">
        {{ count }}
      </span>
    </div>

    <!-- Desktop controls: search field, filters, primary actions. -->
    <div class="ml-3 hidden min-w-0 flex-1 items-center gap-3 md:flex">
      <slot />
    </div>

    <!-- On a phone the same controls collapse to icons, and the account
         lives here because there is no sidebar to hold it. -->
    <div class="ml-auto flex items-center gap-3.5 md:hidden">
      <slot name="mobile" />
      <UserMenu placement="bottom" :show-name="false" />
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import UserMenu from './UserMenu.vue'

const props = defineProps({
  title: { type: String, required: true },
  // { to, label } for a page that lives inside another.
  parent: { type: Object, default: null },
  // A count beside the title, already formatted. `null` renders nothing.
  count: { type: [String, Number], default: null },
  // The canvas gives table pages 20px gutters and form pages 24 or 28.
  gutter: {
    type: String,
    default: 'sm',
    validator: (value) => ['sm', 'md', 'lg'].includes(value)
  }
})

const paddingClass = computed(
  () =>
    ({
      sm: 'px-4 md:px-5',
      md: 'px-4 md:px-6',
      lg: 'px-4 md:px-7'
    })[props.gutter]
)
</script>
