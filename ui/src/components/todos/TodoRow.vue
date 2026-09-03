<template>
  <div
    class="group flex items-center gap-3 border-b border-line-soft px-4 py-[var(--rowpy)] transition-colors hover:bg-panel-sub md:px-5"
  >
    <input
      type="checkbox"
      :checked="todo.is_completed"
      :disabled="loading"
      class="h-4 w-4 flex-none rounded-sm border-line text-ok focus:ring-accent"
      @change="$emit('toggle', todo.id)"
    />

    <button
      type="button"
      class="min-w-0 flex-1 truncate text-left text-[13.5px] transition-colors"
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

    <span
      class="hidden w-[34px] flex-none rounded-sm py-0.5 text-center font-mono text-[10px] md:block"
      :class="priorityClass"
    >
      {{ todo.priority ? t(`todos.priorityShort.${todo.priority}`) : '—' }}
    </span>

    <span
      class="hidden w-[76px] flex-none truncate font-mono text-[11px] text-ink-2 md:block"
    >
      {{ todo.owner || '—' }}
    </span>

    <span
      class="w-[100px] flex-none truncate text-right font-mono text-[11px] md:w-[118px] md:text-left"
      :class="deadlineClass"
    >
      {{ deadlineText }}
    </span>

    <router-link
      v-if="sourceTitle"
      :to="`/chats/${todo.email_message.uuid || todo.email_message.id}`"
      class="hidden w-[210px] flex-none truncate text-[11.5px] text-accent hover:underline md:block"
      :title="sourceTitle"
    >
      {{ sourceTitle }}
    </router-link>
    <span
      v-else
      class="hidden w-[210px] flex-none text-[11.5px] text-ink-4 md:block"
    >
      —
    </span>

    <button
      type="button"
      class="flex-none text-ink-4 opacity-0 transition-opacity hover:text-bad group-hover:opacity-100"
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
