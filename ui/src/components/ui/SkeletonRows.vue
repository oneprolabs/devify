<template>
  <!-- A skeleton says how much is coming and where it will land; a spinner
       says only "wait". Rows fade out down the list so the bottom reads as
       "and more below" rather than as content that failed to arrive. -->
  <div>
    <div
      v-for="row in rows"
      :key="row.key"
      class="flex items-center gap-3 border-b border-line-soft px-4 py-[13px] md:px-5"
      :style="{ opacity: row.opacity }"
    >
      <span class="h-[9px] w-[70px] flex-none rounded-md bg-chip"></span>
      <span class="flex min-w-0 flex-1 flex-col gap-[7px]">
        <span
          class="h-2.5 rounded-md bg-chip"
          :style="{ width: row.title }"
        ></span>
        <span
          class="h-2 rounded bg-line-soft"
          :style="{ width: row.body }"
        ></span>
      </span>
      <span class="h-2 w-20 flex-none rounded bg-line-soft"></span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  count: { type: Number, default: 4 }
})

// Fixed widths rather than random ones, so the placeholder does not flicker
// into a different shape on every render.
const WIDTHS = [
  ['62%', '88%'],
  ['47%', '76%'],
  ['70%', '58%'],
  ['54%', '81%'],
  ['66%', '72%']
]

const rows = computed(() =>
  Array.from({ length: props.count }, (_, index) => {
    const [title, body] = WIDTHS[index % WIDTHS.length]
    return {
      key: index,
      title,
      body,
      opacity: index === props.count - 1 ? 0.55 : 1
    }
  })
)
</script>
