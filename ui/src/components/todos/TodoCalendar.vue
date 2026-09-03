<template>
  <div class="hidden flex-col md:flex">
    <div
      class="flex h-11 flex-shrink-0 items-center gap-4 border-b border-line px-5"
    >
      <button
        type="button"
        class="rounded p-1 text-ink-2 transition-colors hover:bg-chip hover:text-ink"
        :aria-label="t('common.previous')"
        @click="$emit('previous')"
      >
        <svg
          class="h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            d="M15 19l-7-7 7-7"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
      <span class="text-[13px] font-semibold text-ink">{{ label }}</span>
      <div
        class="order-last ml-auto flex h-8 items-center overflow-hidden rounded-md border border-line"
      >
        <button
          v-for="(option, index) in modes"
          :key="option.value"
          type="button"
          class="font-display h-8 px-3 text-[12px] transition-colors"
          :class="[
            mode === option.value
              ? 'bg-accent-soft font-medium text-accent'
              : 'text-ink-2 hover:bg-chip',
            index ? 'border-l border-line' : ''
          ]"
          @click="$emit('update:mode', option.value)"
        >
          {{ option.label }}
        </button>
      </div>
      <button
        type="button"
        class="rounded p-1 text-ink-2 transition-colors hover:bg-chip hover:text-ink"
        :aria-label="t('common.next')"
        @click="$emit('next')"
      >
        <svg
          class="h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            d="M9 5l7 7-7 7"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </div>

    <div class="p-5">
      <div class="mb-2 grid grid-cols-7 gap-2">
        <span
          v-for="day in weekDays"
          :key="day"
          class="py-1 text-center font-mono text-[10.5px] text-ink-4"
        >
          {{ day }}
        </span>
      </div>

      <div class="grid grid-cols-7 gap-2">
        <button
          v-for="(date, index) in days"
          :key="index"
          type="button"
          class="min-h-[80px] rounded border p-2 text-left transition-colors"
          :class="[
            date.isCurrentMonth
              ? 'border-line bg-panel hover:border-accent'
              : 'border-line-soft bg-app-sub text-ink-4',
            date.isToday ? 'ring-1 ring-accent' : '',
            isSelected(date.date) ? 'border-accent bg-accent-soft' : ''
          ]"
          @click="$emit('select', date.date)"
        >
          <span class="mb-1 block font-mono text-[11px] font-medium">
            {{ date.day }}
          </span>
          <span class="flex max-h-[60px] flex-col gap-1 overflow-hidden">
            <span
              v-for="todo in todosFor(date.date).slice(0, 3)"
              :key="todo.id"
              class="truncate rounded-sm px-1 py-0.5 text-[10.5px]"
              :class="chipClass(todo)"
              @click.stop="$emit('open', todo, date.date)"
            >
              {{ todo.content }}
            </span>
            <span
              v-if="todosFor(date.date).length > 3"
              class="rounded-sm bg-chip px-1 py-0.5 text-[10.5px] text-ink-2"
            >
              {{
                t('todos.calendar.moreTodos', {
                  count: todosFor(date.date).length - 3
                })
              }}
            </span>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  days: { type: Array, required: true },
  weekDays: { type: Array, required: true },
  label: { type: String, default: '' },
  selectedDate: { type: [Date, null], default: null },
  // (date) => todos due that day
  todosFor: { type: Function, required: true },
  mode: { type: String, default: 'month' }
})

defineEmits(['previous', 'next', 'select', 'open', 'update:mode'])

const { t } = useI18n()

const modes = computed(() => [
  { value: 'month', label: t('todos.calendar.monthView') },
  { value: 'week', label: t('todos.calendar.weekView') }
])

const isSelected = (date) =>
  Boolean(props.selectedDate) &&
  date.toDateString() === props.selectedDate.toDateString()

const chipClass = (todo) => {
  if (todo.is_completed) return 'bg-chip text-ink-3 line-through'
  if (todo.priority === 'high') return 'bg-bad-soft text-bad'
  if (todo.priority === 'medium') return 'bg-warn-soft text-warn'
  return 'bg-accent-soft text-accent'
}
</script>
