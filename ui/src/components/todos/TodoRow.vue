<template>
  <div
    class="group relative flex items-start gap-3 border-b border-line-soft px-4 py-3 transition-colors hover:bg-panel-sub md:items-center md:px-5 md:py-[var(--rowpy)]"
  >
    <input
      type="checkbox"
      :checked="todo.is_completed"
      :disabled="loading"
      class="mt-px h-[22px] w-[22px] flex-none rounded-md border-line text-ok focus:ring-accent md:mt-0 md:h-[18px] md:w-[18px] md:rounded-sm"
      @change="$emit('toggle', todo.id)"
    />

    <!-- Narrow screens have no columns, so the same fields stack under the
         content the way the canvas draws them. -->
    <div class="flex min-w-0 flex-1 flex-col gap-[5px] md:contents">
      <button
        type="button"
        class="text-left text-[calc(13.5px*var(--fs))] leading-[1.45] transition-colors md:min-w-0 md:flex-1 md:truncate md:leading-[calc(18px*var(--fs))]"
        :class="
          todo.is_completed
            ? 'text-ink-3 line-through'
            : 'text-ink hover:text-accent'
        "
        :title="todo.content"
        @click="$emit('edit', todo)"
      >
        {{ todo.content }}
      </button>

      <div class="flex items-center gap-[7px] md:contents">
        <span
          class="flex-none rounded-sm px-1.5 py-0.5 text-center font-mono text-[calc(10px*var(--fs))] md:w-[34px] md:flex-none md:px-0 md:py-0.5"
          :class="priorityClass"
        >
          {{ todo.priority ? t(`todos.priorityShort.${todo.priority}`) : '—' }}
        </span>

        <span
          class="order-3 truncate font-mono text-[calc(10.5px*var(--fs))] text-ink-4 md:order-none md:w-[76px] md:flex-none md:text-[calc(11px*var(--fs))] md:text-ink-2"
        >
          {{ todo.owner || '—' }}
        </span>

        <span
          class="order-2 flex-none truncate font-mono text-[calc(10.5px*var(--fs))] md:order-none md:w-[118px] md:text-[calc(11px*var(--fs))]"
          :class="deadlineClass"
        >
          {{ deadlineText }}
        </span>
      </div>

    <router-link
      v-if="sourceTitle"
      :to="`/chats/${todo.email_message.uuid || todo.email_message.id}`"
      class="truncate text-[calc(11px*var(--fs))] text-accent hover:underline md:w-[210px] md:flex-none md:text-[calc(11.5px*var(--fs))]"
      :title="sourceTitle"
    >
      {{ sourceTitle }}
    </router-link>
    <span
      v-else
      class="hidden text-[calc(11.5px*var(--fs))] text-ink-4 md:block md:w-[210px] md:flex-none"
    >
      —
    </span>
    </div>

    <button
      type="button"
      class="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm bg-panel-sub p-1 text-ink-4 opacity-0 transition-opacity hover:text-bad group-hover:opacity-100"
      :disabled="loading"
      :aria-label="t('todos.delete')"
      @click="$emit('delete', todo.id)"
    >
      <svg
        class="h-3.5 w-3.5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path
          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePreferencesStore } from '@/store/preferences'
import { formatDate } from '@/utils/timezone'

const props = defineProps({
  todo: { type: Object, required: true },
  loading: { type: Boolean, default: false }
})

defineEmits(['toggle', 'edit', 'delete'])

const { t, locale } = useI18n()
const preferences = usePreferencesStore()

const PRIORITY_CLASSES = {
  high: 'bg-bad-soft text-bad',
  medium: 'bg-warn-soft text-warn',
  low: 'bg-chip text-ink-3'
}
const priorityClass = computed(
  () => PRIORITY_CLASSES[props.todo.priority] || 'text-ink-4'
)

const sourceTitle = computed(() => {
  const email = props.todo.email_message
  if (!email) return ''
  return email.summary_title || email.subject || ''
})

const daysAway = computed(() => {
  if (!props.todo.deadline || props.todo.is_completed) return null
  const diffMs = new Date(props.todo.deadline) - new Date()
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24))
})

// A deadline is only useful next to how near it is, which is what makes an
// overdue row readable at a glance.
const deadlineText = computed(() => {
  if (!props.todo.deadline) return '—'

  const zone = preferences.currentTimezone
  const language = locale.value
  const clock = formatDate(props.todo.deadline, zone, 'HH:mm', language)
  const day = formatDate(props.todo.deadline, zone, 'MM-dd', language)
  const days = daysAway.value

  // The column is 118px: a clock and a "3 days left" together do not fit, and
  // the nearness matters more than the minute.
  let note = ''
  if (days !== null && days < 0) {
    note = t('todos.overdueBy', { days: Math.abs(days) })
  } else if (days === 0) {
    note = t('todos.dueTodayShort')
  } else if (days !== null && days <= 3) {
    note = t('todos.dueIn', { days })
  }

  if (note) return `${day} · ${note}`
  return clock === '00:00' ? day : `${day} ${clock}`
})

const deadlineClass = computed(() => {
  const days = daysAway.value
  if (days === null) return 'text-ink-4'
  if (days < 0) return 'text-bad'
  if (days <= 3) return 'text-warn'
  return 'text-ink-2'
})
</script>
