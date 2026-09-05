<template>
  <!-- A skeleton says how much is coming and where it will land; a spinner
       says only "wait". Rows fade out down the list so the bottom reads as
       "and more below" rather than as content that failed to arrive.

       The two shapes mirror the two real layouts: columns on a desktop row,
       a stacked card on a phone, so nothing jumps when the data lands. -->
  <div>
    <div
      v-for="row in rows"
      :key="row.key"
      class="px-4 py-[13px] md:px-5"
      :class="row.last ? '' : 'border-b border-line-soft'"
      :style="{ opacity: row.opacity }"
    >
      <div class="flex flex-col gap-[7px] md:hidden">
        <span class="flex items-center gap-3">
          <span class="h-[9px] w-[70px] flex-none rounded-[5px] bg-chip"></span>
          <span class="ml-auto h-2 w-16 flex-none rounded-sm bg-line-soft"></span>
        </span>
        <span
          class="h-2.5 rounded-[5px] bg-chip"
          :style="{ width: row.title }"
        ></span>
        <span
          class="h-2 rounded-sm bg-line-soft"
          :style="{ width: row.body }"
        ></span>
      </div>

      <div class="hidden items-center gap-3 md:flex">
        <span class="h-[9px] w-[70px] flex-none rounded-[5px] bg-chip"></span>
        <span class="flex min-w-0 flex-1 flex-col gap-[7px]">
          <span
            class="h-2.5 rounded-[5px] bg-chip"
            :style="{ width: row.title }"
          ></span>
          <span
            class="h-2 rounded-sm bg-line-soft"
            :style="{ width: row.body }"
          ></span>
        </span>
        <span class="h-2 w-20 flex-none rounded-sm bg-line-soft"></span>
      </div>
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
    const last = index === props.count - 1
    return { key: index, title, body, last, opacity: last ? 0.55 : 1 }
  })
)
</script>
