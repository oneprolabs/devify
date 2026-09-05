<template>
  <header
    class="flex h-[53px] flex-shrink-0 items-center gap-[9px] border-b border-line bg-app md:h-[57px] md:gap-3"
    :class="paddingClass"
  >
    <!-- A phone has no sidebar to go back through, so a nested page puts
         the way out in the header and stacks the parent above the title. -->
    <router-link
      v-if="parent"
      :to="parent.to"
      class="flex-none text-ink transition-colors hover:text-ink-2 md:hidden"
      :aria-label="parent.label"
    >
      <svg
        class="h-5 w-5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path
          d="M15 5l-7 7 7 7"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </router-link>

    <div
      class="flex min-w-0 flex-col gap-px md:flex-row md:items-baseline md:gap-2"
    >
      <template v-if="parent">
        <span class="flex-none text-[calc(10px*var(--fs))] text-ink-3 md:hidden">
          {{ parent.label }}
        </span>
        <router-link
          v-if="!parentMobileOnly"
          :to="parent.to"
          class="hidden flex-none text-[calc(12.5px*var(--fs))] text-ink-3 transition-colors hover:text-ink md:block"
        >
          {{ parent.label }}
        </router-link>
        <span
          v-if="!parentMobileOnly"
          class="hidden flex-none text-[calc(12.5px*var(--fs))] text-ink-4 md:block"
        >
          /
        </span>
      </template>

      <div class="flex min-w-0 items-baseline gap-[7px] md:contents">
        <h1
          class="truncate font-semibold text-ink md:text-[calc(14.5px*var(--fs))]"
          :class="parent ? 'text-[calc(15px*var(--fs))]' : 'text-base'"
        >
          {{ title }}
        </h1>
        <span
          v-if="count !== null"
          class="flex-none font-mono text-[calc(10.5px*var(--fs))] text-ink-3 md:text-[calc(11px*var(--fs))]"
        >
          {{ count }}
        </span>
      </div>
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
  // Billing sits under Settings on a phone but stands alone on a desktop,
  // which is how the canvas draws it.
  parentMobileOnly: { type: Boolean, default: false },
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
