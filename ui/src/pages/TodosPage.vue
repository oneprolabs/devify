<template>
  <AppLayout :padded="false">
    <PageHeader :title="t('todos.title')" :count="openCountLabel">
      <label
        class="flex h-8 max-w-[360px] flex-1 items-center gap-2 rounded-md border border-line bg-panel-sub px-2.5"
      >
        <svg
          class="h-3.5 w-3.5 flex-none text-ink-3"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-4.5-4.5" stroke-linecap="round" />
        </svg>
        <input
          v-model="filters.search"
          type="text"
          :placeholder="t('todos.searchPlaceholder')"
          class="min-w-0 flex-1 border-0 bg-transparent p-0 text-[12.5px] text-ink placeholder:text-ink-3 focus:outline-none focus:ring-0"
        />
      </label>

      <div class="ml-auto flex items-center gap-[7px]">
        <div
          class="flex h-8 items-center overflow-hidden rounded-md border border-line"
        >
          <button
            v-for="(mode, index) in viewModes"
            :key="mode.value"
            type="button"
            class="font-display flex h-8 items-center gap-1.5 px-3 text-[12.5px] transition-colors"
            :class="[
              viewMode === mode.value
                ? 'bg-accent-soft font-medium text-accent'
                : 'text-ink-2 hover:bg-chip',
              index ? 'border-l border-line' : ''
            ]"
            @click="viewMode = mode.value"
          >
            <component :is="mode.icon" class="h-[13px] w-[13px]" />
            {{ mode.label }}
          </button>
        </div>

        <FilterSelect
          :label="groupLabel"
          :options="groupOptions"
          :model-value="groupBy"
          @update:model-value="groupBy = $event"
        />

        <button
          type="button"
          class="font-display flex h-8 items-center gap-[7px] rounded-md bg-accent px-[13px] text-[12.5px] font-medium text-accent-on transition-opacity hover:opacity-90"
          @click="openNewTodo"
        >
          <svg
            class="h-3.5 w-3.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            aria-hidden="true"
          >
            <path d="M12 5v14M5 12h14" stroke-linecap="round" />
          </svg>
          {{ t('todos.add') }}
        </button>
      </div>

      <template #mobile>
        <button
          type="button"
          class="text-ink-2"
          :aria-label="t('todos.add')"
          @click="openNewTodo"
        >
          <svg
            class="h-[19px] w-[19px]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            aria-hidden="true"
          >
            <path d="M12 5v14M5 12h14" stroke-linecap="round" />
          </svg>
        </button>
      </template>
    </PageHeader>

    <TodoStatStrip
      v-model="timeRange"
      :total="stats?.total || 0"
      :completed="stats?.completed || 0"
      :incomplete="stats?.incomplete || 0"
      :completion-rate="completionRate"
      :by-priority="openByPriority"
      :ranges="timeRanges"
    />

    <!-- Status chips: the one filter worth reaching for without a menu. -->
    <div
      class="flex h-11 flex-shrink-0 items-center gap-1.5 overflow-x-auto border-b border-line px-4 md:px-5"
    >
      <button
        v-for="chip in statusChips"
        :key="String(chip.value)"
        type="button"
        class="font-display flex-none rounded-md px-3 py-1.5 text-xs transition-colors"
        :class="
          filters.is_completed === chip.value
            ? 'bg-accent font-medium text-accent-on'
            : 'border border-line text-ink-2'
        "
        @click="filters.is_completed = chip.value"
      >
        {{ chip.label }}
      </button>

      <template v-if="timeRange === 'custom'">
        <input
          v-model="customStartDate"
          type="date"
          class="h-8 flex-none rounded-md border border-line bg-panel-sub px-2 font-mono text-[11.5px] text-ink focus:border-accent focus:outline-none focus:ring-0"
          @change="handleCustomDateChange"
        />
        <span class="flex-none text-ink-4">–</span>
        <input
          v-model="customEndDate"
          type="date"
          class="h-8 flex-none rounded-md border border-line bg-panel-sub px-2 font-mono text-[11.5px] text-ink focus:border-accent focus:outline-none focus:ring-0"
          @change="handleCustomDateChange"
        />
      </template>

      <FilterSelect
        class="ml-auto hidden md:block"
        :label="priorityLabel"
        :options="priorityOptions"
        :model-value="filters.priority"
        @update:model-value="filters.priority = $event"
      />
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <TodoCalendar
        v-if="viewMode === 'calendar'"
        :days="calendarDays"
        :week-days="weekDays"
        :label="
          calendarViewMode === 'week' ? currentWeekLabel : currentMonthLabel
        "
        :selected-date="selectedDate"
        :todos-for="getTodosForDate"
        @previous="previousPeriod"
        @next="nextPeriod"
        @select="selectDate"
        @open="handleCalendarTodoClick"
      />

      <!-- Column headings, matching the row widths below. -->
      <div
        class="sticky top-0 z-10 hidden h-[30px] items-center gap-3 bg-app px-5 font-mono text-[10.5px] tracking-[0.06em] text-ink-4 md:flex"
      >
        <div class="w-4 flex-none"></div>
        <div class="min-w-0 flex-1">{{ t('todos.content') }}</div>
        <div class="w-[34px] flex-none text-center">
          {{ t('todos.priorityColumn') }}
        </div>
        <div class="w-[76px] flex-none">{{ t('todos.owner') }}</div>
        <div class="w-[118px] flex-none">{{ t('todos.deadline') }}</div>
        <div class="w-[210px] flex-none">{{ t('todos.sourceChat') }}</div>
        <div class="w-3.5 flex-none"></div>
      </div>

      <div v-if="loading" class="flex flex-col items-center gap-2 py-16">
        <span
          class="h-8 w-8 animate-spin rounded-full border-b-2 border-accent"
        ></span>
        <p class="text-sm text-ink-3">{{ t('common.loading') }}</p>
      </div>

      <p
        v-else-if="!visibleTodos.length"
        class="py-16 text-center text-sm italic text-ink-3"
      >
        {{ selectedDate ? t('todos.noTodosForDate') : t('todos.noTodos') }}
      </p>

      <template v-else>
        <template v-for="group in orderedGroups" :key="group.key">
          <div
            class="flex h-[34px] items-center gap-2 border-y border-line bg-panel-sub px-4 md:px-5"
          >
            <span
              class="h-[5px] w-[5px] rounded-full"
              :class="group.dotClass"
            ></span>
            <span
              class="font-display text-[11.5px] font-semibold tracking-[0.02em]"
              :class="group.labelClass"
            >
              {{ group.label }}
            </span>
            <span class="font-mono text-[10.5px] text-ink-4">
              {{ t('todos.groupCount', { count: group.todos.length }) }}
            </span>
          </div>

          <TodoRow
            v-for="todo in group.todos"
            :key="todo.id"
            :todo="todo"
            :loading="todoLoading[todo.id]"
            @toggle="handleToggleTodo"
            @edit="handleEditTodo"
            @delete="handleDeleteTodo"
          />
        </template>
      </template>
    </div>

    <BaseModal
      :show="showTodoEditor"
      :title="editingTodo ? t('todos.editTodo') : t('todos.addTodo')"
      @close="closeTodoEditor"
    >
      <TodoEditor
        :todo="editingTodo"
        :email-message-id="null"
        :loading="savingTodo"
        @save="handleSaveTodo"
        @cancel="closeTodoEditor"
      />
    </BaseModal>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePreferencesStore } from '@/store/preferences'
import { formatDate as formatDateUtil } from '@/utils/timezone'
import { extractErrorMessage } from '@/utils/api'
import { todosApi } from '@/api/todos'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import FilterSelect from '@/components/ui/FilterSelect.vue'
import TodoEditor from '@/components/TodoEditor.vue'
import TodoRow from '@/components/todos/TodoRow.vue'
import TodoCalendar from '@/components/todos/TodoCalendar.vue'
import TodoStatStrip from '@/components/todos/TodoStatStrip.vue'
import { IconApps, IconTodos } from '@/components/layout/navIcons'

const { t, locale } = useI18n()
const preferencesStore = usePreferencesStore()

const todos = ref([])
const stats = ref(null)
const loading = ref(false)
const currentMonth = ref(new Date())
const selectedDate = ref(null)
const viewMode = ref('list') // 'list' or 'calendar', default to 'list'
const timeRange = ref('month') // 'week', 'month', 'quarter', 'custom'
const calendarViewMode = ref('month') // 'month' or 'week' for calendar view
const customStartDate = ref('')
const customEndDate = ref('')

const filters = ref({
  is_completed: null,
  priority: null,
  owner: '',
  search: ''
})

// Active filters for display
const activeFilters = computed(() => {
  const active = {}
  if (filters.value.is_completed !== null) {
    active.is_completed = {
      label: t('todos.filters.status'),
      value: filters.value.is_completed
        ? t('todos.filters.completed')
        : t('todos.filters.incomplete')
    }
  }
  if (filters.value.priority) {
    active.priority = {
      label: t('todos.filters.priority'),
      value: t(`todos.priority.${filters.value.priority}`)
    }
  }
  if (filters.value.owner) {
    active.owner = {
      label: t('todos.filters.owner'),
      value: filters.value.owner
    }
  }
  if (filters.value.search) {
    active.search = {
      label: t('common.search'),
      value: filters.value.search
    }
  }
  return active
})

const hasActiveFilters = computed(() => {
  return Object.keys(activeFilters.value).length > 0
})

const showTodoEditor = ref(false)
const editingTodo = ref(null)
const savingTodo = ref(false)
const todoLoading = ref({})
const errorMessage = ref('')
const successMessage = ref('')
const groupBy = ref('email') // 'date', 'owner', 'priority', 'category', 'location', 'email'

// Time range options (no more than 1 year)
const timeRanges = computed(() => [
  { value: 'month', label: t('todos.timeRange.month') },
  { value: 'week', label: t('todos.timeRange.week') },
  { value: 'quarter', label: t('todos.timeRange.quarter') },
  { value: 'custom', label: t('todos.timeRange.custom') }
])

// Get time range dates for display (helper function)
const getTimeRangeDates = () => {
  const now = new Date()
  let start, end

  switch (timeRange.value) {
    case 'week':
      // Current week (Monday to Sunday)
      const weekRange = getWeekRangeForDate(now)
      start = weekRange.start
      end = weekRange.end
      break
    case 'month':
      // Current month (use actual current date, not calendar month)
      const year = now.getFullYear()
      const month = now.getMonth()
      start = new Date(year, month, 1)
      end = new Date(year, month + 1, 0, 23, 59, 59, 999)
      break
    case 'quarter':
      // Current quarter
      const quarterMonth = Math.floor(now.getMonth() / 3) * 3
      start = new Date(now.getFullYear(), quarterMonth, 1)
      end = new Date(now.getFullYear(), quarterMonth + 3, 0, 23, 59, 59, 999)
      break
    default:
      // Fallback to current month (use actual current date)
      const defaultYear = now.getFullYear()
      const defaultMonth = now.getMonth()
      start = new Date(defaultYear, defaultMonth, 1)
      end = new Date(defaultYear, defaultMonth + 1, 0, 23, 59, 59, 999)
  }

  // Format dates as YYYY-MM-DD using local timezone (avoid timezone offset issues)
  const formatDateLocal = (date) => {
    if (!date) return ''
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }

  return {
    start: formatDateLocal(start),
    end: formatDateLocal(end)
  }
}

// Display dates (computed based on time range)
const displayStartDate = computed({
  get() {
    if (timeRange.value === 'custom') {
      return customStartDate.value
    }
    return getTimeRangeDates().start
  },
  set(value) {
    if (timeRange.value === 'custom') {
      customStartDate.value = value
    }
  }
})

const displayEndDate = computed({
  get() {
    if (timeRange.value === 'custom') {
      return customEndDate.value
    }
    return getTimeRangeDates().end
  },
  set(value) {
    if (timeRange.value === 'custom') {
      customEndDate.value = value
    }
  }
})

// Time range label for display
const timeRangeLabel = computed(() => {
  if (timeRange.value === 'custom') {
    if (customStartDate.value && customEndDate.value) {
      return `${customStartDate.value} - ${customEndDate.value}`
    }
    return t('todos.timeRange.custom')
  }
  return timeRanges.value.find((r) => r.value === timeRange.value)?.label || ''
})

const weekDays = computed(() => {
  const days =
    locale.value === 'zh-CN'
      ? ['日', '一', '二', '三', '四', '五', '六']
      : ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  return days
})

const currentMonthLabel = computed(() => {
  const year = currentMonth.value.getFullYear()
  const month = currentMonth.value.getMonth()
  const date = new Date(year, month, 1)
  return formatDateUtil(
    date.toISOString(),
    preferencesStore.currentTimezone,
    locale.value === 'zh-CN' ? 'yyyy年MM月' : 'MMMM yyyy',
    locale.value
  )
})

const currentWeekLabel = computed(() => {
  const weekRange = getWeekRangeForDate(currentMonth.value)
  const monday = weekRange.start
  const sunday = weekRange.end

  const startStr = formatDateUtil(
    monday.toISOString(),
    preferencesStore.currentTimezone,
    locale.value === 'zh-CN' ? 'MM月dd日' : 'MMM dd',
    locale.value
  )
  const endStr = formatDateUtil(
    sunday.toISOString(),
    preferencesStore.currentTimezone,
    locale.value === 'zh-CN' ? 'MM月dd日' : 'MMM dd',
    locale.value
  )

  return locale.value === 'zh-CN'
    ? `${startStr} - ${endStr}`
    : `${startStr} - ${endStr}`
})

const completionRate = computed(() => {
  if (!stats.value || stats.value.total === 0) return 0
  return Math.round((stats.value.completed / stats.value.total) * 100)
})

const calendarDays = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = []

  if (calendarViewMode.value === 'week') {
    // Week view: show only 7 days of the current week
    const monday = getMondayOfWeek(currentMonth.value)

    for (let i = 0; i < 7; i++) {
      const date = new Date(monday)
      date.setDate(monday.getDate() + i)
      const dateCopy = new Date(date)
      dateCopy.setHours(0, 0, 0, 0)

      days.push({
        date: dateCopy,
        day: date.getDate(),
        isCurrentMonth: true, // In week view, all days are considered current
        isToday: dateCopy.getTime() === today.getTime()
      })
    }
  } else {
    // Month view: show full month (42 days, 6 weeks)
    const year = currentMonth.value.getFullYear()
    const month = currentMonth.value.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const startDate = new Date(firstDay)
    startDate.setDate(startDate.getDate() - startDate.getDay())

    for (let i = 0; i < 42; i++) {
      const date = new Date(startDate)
      date.setDate(startDate.getDate() + i)
      const dateCopy = new Date(date)
      dateCopy.setHours(0, 0, 0, 0)

      days.push({
        date: dateCopy,
        day: date.getDate(),
        isCurrentMonth: date.getMonth() === month,
        isToday: dateCopy.getTime() === today.getTime()
      })
    }
  }

  return days
})

const selectedDateTodos = computed(() => {
  let dateTodos = []

  if (selectedDate.value) {
    // Show todos for selected date
    dateTodos = getTodosForDate(selectedDate.value)
  } else {
    // Show todos based on calendar view mode and current month/week
    if (viewMode.value === 'calendar') {
      if (calendarViewMode.value === 'week') {
        // Week view: show todos for current week
        const weekRange = getWeekRangeForDate(currentMonth.value)
        dateTodos = todos.value.filter((todo) => {
          if (!todo.deadline) return false
          const todoDate = new Date(todo.deadline)
          return todoDate >= weekRange.start && todoDate <= weekRange.end
        })
      } else {
        // Month view: show todos for current month
        dateTodos = todos.value.filter((todo) => {
          if (!todo.deadline) return false
          const todoDate = new Date(todo.deadline)
          const year = todoDate.getFullYear()
          const month = todoDate.getMonth()
          const currentYear = currentMonth.value.getFullYear()
          const currentMonthIndex = currentMonth.value.getMonth()
          return year === currentYear && month === currentMonthIndex
        })
      }
    } else {
      // List view: show all todos for current month (default view)
      dateTodos = todos.value.filter((todo) => {
        if (!todo.deadline) return false
        const todoDate = new Date(todo.deadline)
        const year = todoDate.getFullYear()
        const month = todoDate.getMonth()
        const currentYear = currentMonth.value.getFullYear()
        const currentMonthIndex = currentMonth.value.getMonth()
        return year === currentYear && month === currentMonthIndex
      })
    }
  }

  // Add temporary new todo if exists
  const allTodos = dateTodos

  // Sort by created_at (timeline order - oldest first)
  return allTodos.sort((a, b) => {
    // Temp todos go to the end
    if (a.id && a.id.toString().startsWith('temp-')) return 1
    if (b.id && b.id.toString().startsWith('temp-')) return 1

    // Sort by created_at from oldest to newest (timeline order)
    if (a.created_at && b.created_at) {
      return new Date(a.created_at) - new Date(b.created_at)
    }
    if (a.created_at && !b.created_at) return -1
    if (!a.created_at && b.created_at) return 1
    return 0
  })
})

// Group todos by selected method
// --- What the canvas header and grouped table need -------------------------

const viewModes = computed(() => [
  { value: 'list', label: t('todos.view.list'), icon: IconTodos },
  { value: 'calendar', label: t('todos.view.calendar'), icon: IconApps }
])

const groupOptions = computed(() => [
  { value: 'date', label: t('todos.groupBy.date') },
  { value: 'email', label: t('todos.groupBy.subject') },
  { value: 'owner', label: t('todos.groupBy.owner') },
  { value: 'priority', label: t('todos.groupBy.priority') },
  { value: 'category', label: t('todos.groupBy.category') },
  { value: 'location', label: t('todos.groupBy.location') }
])
const groupLabel = computed(
  () =>
    `${t('todos.groupByLabel')}${
      groupOptions.value.find((option) => option.value === groupBy.value)
        ?.label || ''
    }`
)

const statusChips = computed(() => [
  { value: null, label: t('todos.filters.all') },
  { value: false, label: t('todos.filters.incomplete') },
  { value: true, label: t('todos.filters.completed') }
])

const priorityOptions = computed(() => [
  { value: null, label: t('todos.filters.all') },
  { value: 'high', label: t('todos.priority.high') },
  { value: 'medium', label: t('todos.priority.medium') },
  { value: 'low', label: t('todos.priority.low') }
])
const priorityLabel = computed(
  () =>
    `${t('todos.priority.label')}：${
      priorityOptions.value.find(
        (option) => option.value === filters.value.priority
      )?.label || ''
    }`
)

const openCountLabel = computed(() =>
  stats.value ? t('todos.openCount', { count: stats.value.incomplete }) : null
)

const openByPriority = computed(() => {
  const open = todos.value.filter((todo) => !todo.is_completed)
  return {
    high: open.filter((todo) => todo.priority === 'high').length,
    medium: open.filter((todo) => todo.priority === 'medium').length,
    low: open.filter((todo) => todo.priority === 'low').length
  }
})

const visibleTodos = computed(() => selectedDateTodos.value)

// Late work is its own group at the top: it is not "another day", it is the
// thing to deal with first.
const isOverdue = (todo) =>
  !todo.is_completed && todo.deadline && new Date(todo.deadline) < new Date()

const orderedGroups = computed(() => {
  const overdue = visibleTodos.value.filter(isOverdue)
  const groups = []

  if (overdue.length) {
    groups.push({
      key: 'overdue',
      label: t('todos.overdueGroup'),
      todos: overdue,
      dotClass: 'bg-bad',
      labelClass: 'text-bad'
    })
  }

  const rest = new Set(overdue.map((todo) => todo.id))
  Object.entries(groupedTodos.value).forEach(([key, items]) => {
    const remaining = items.filter((todo) => !rest.has(todo.id))
    if (!remaining.length) return
    groups.push({
      key,
      label: getGroupLabel(key, groupBy.value),
      todos: remaining,
      dotClass: 'bg-ink-4',
      labelClass: 'text-ink-2'
    })
  })

  return groups
})

const openNewTodo = () => {
  editingTodo.value = null
  showTodoEditor.value = true
}

const groupedTodos = computed(() => {
  if (!selectedDateTodos.value.length) return {}

  const grouped = {}

  selectedDateTodos.value.forEach((todo) => {
    let key = ''

    switch (groupBy.value) {
      case 'date':
        // Group by deadline date
        if (todo.deadline) {
          const date = new Date(todo.deadline)
          date.setHours(0, 0, 0, 0)
          key = date.getTime().toString()
        } else {
          key = 'no-deadline'
        }
        break
      case 'owner':
        key = todo.owner || ''
        break
      case 'priority':
        key = todo.priority || 'none'
        break
      case 'category':
        // Use email_message metadata.category, or 'no-category'
        if (
          todo.email_message &&
          todo.email_message.metadata &&
          todo.email_message.metadata.category
        ) {
          const categories = Array.isArray(todo.email_message.metadata.category)
            ? todo.email_message.metadata.category
            : [todo.email_message.metadata.category]
          key = categories.length > 0 ? categories[0] : 'no-category'
        } else {
          key = 'no-category'
        }
        break
      case 'location':
        key = todo.location || ''
        break
      case 'email':
        // Use email_message summary_title or subject, or 'no-email'
        if (todo.email_message) {
          key =
            todo.email_message.summary_title ||
            todo.email_message.subject ||
            'no-title'
        } else {
          key = 'no-email'
        }
        break
      default:
        key = todo.owner || ''
    }

    if (!grouped[key]) {
      grouped[key] = []
    }
    grouped[key].push(todo)
  })

  // Sort groups based on group type
  const sortedGroups = {}
  const keys = Object.keys(grouped)

  let sortedKeys = []
  switch (groupBy.value) {
    case 'date':
      // Sort by date (timestamp), no-deadline last
      sortedKeys = keys.sort((a, b) => {
        if (a === 'no-deadline' && b !== 'no-deadline') return 1
        if (a !== 'no-deadline' && b === 'no-deadline') return -1
        return parseInt(a) - parseInt(b)
      })
      break
    case 'priority':
      // Sort: high, medium, low, none
      const priorityOrder = { high: 1, medium: 2, low: 3, none: 4 }
      sortedKeys = keys.sort((a, b) => {
        return (priorityOrder[a] || 99) - (priorityOrder[b] || 99)
      })
      break
    case 'owner':
    case 'location':
    case 'category':
      // Sort: non-empty first, then alphabetically
      sortedKeys = keys.sort((a, b) => {
        if (
          (a === '' || a === 'no-category') &&
          b !== '' &&
          b !== 'no-category'
        )
          return 1
        if (
          a !== '' &&
          a !== 'no-category' &&
          (b === '' || b === 'no-category')
        )
          return -1
        return a.localeCompare(b)
      })
      break
    case 'email':
      // Sort: no-email last, then alphabetically
      sortedKeys = keys.sort((a, b) => {
        if (a === 'no-email' && b !== 'no-email') return 1
        if (a !== 'no-email' && b === 'no-email') return -1
        return a.localeCompare(b)
      })
      break
    default:
      sortedKeys = keys
  }

  sortedKeys.forEach((key) => {
    sortedGroups[key] = grouped[key]
  })

  return sortedGroups
})

// Helper function to get Monday of the week for a given date
const getMondayOfWeek = (date) => {
  const dateCopy = new Date(date)
  dateCopy.setHours(0, 0, 0, 0)
  const dayOfWeek = dateCopy.getDay()
  const monday = new Date(dateCopy)
  monday.setDate(dateCopy.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1))
  monday.setHours(0, 0, 0, 0)
  return monday
}

// Helper function to get week range (Monday to Sunday) for a given date
const getWeekRangeForDate = (date) => {
  const monday = getMondayOfWeek(date)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  sunday.setHours(23, 59, 59, 999)
  return { start: monday, end: sunday }
}

// Get group label
const getGroupLabel = (key, type) => {
  if (type === 'date') {
    if (key === 'no-deadline') return t('todos.groupBy.noDeadline')
    const date = new Date(parseInt(key))
    return formatSelectedDate(date)
  } else if (type === 'owner') {
    return key || t('todos.filters.owner') + ': ' + t('todos.notSet')
  } else if (type === 'priority') {
    if (key === 'none')
      return t('todos.priority.label') + ': ' + t('todos.notSet')
    return t('todos.priority.label') + ': ' + t(`todos.priority.${key}`)
  } else if (type === 'category') {
    if (key === 'no-category')
      return t('metadata.category.title') + ': ' + t('todos.notSet')
    return t('metadata.category.title') + ': ' + key
  } else if (type === 'location') {
    return key || t('todos.location') + ': ' + t('todos.notSet')
  } else if (type === 'email') {
    if (key === 'no-email') return t('todos.groupBy.noSubject')
    if (key === 'no-title') return t('todos.groupBy.noTitle')
    return key
  }
  return key
}

// Get time range based on selected range type
const getTimeRange = () => {
  const now = new Date()
  let start, end

  switch (timeRange.value) {
    case 'week':
      // Current week (Monday to Sunday)
      const weekRange = getWeekRangeForDate(now)
      start = weekRange.start
      end = weekRange.end
      break
    case 'month':
      // Current month (use actual current date, not calendar month)
      const year = now.getFullYear()
      const month = now.getMonth()
      start = new Date(year, month, 1)
      end = new Date(year, month + 1, 0, 23, 59, 59, 999)
      break
    case 'quarter':
      // Current quarter
      const quarterMonth = Math.floor(now.getMonth() / 3) * 3
      start = new Date(now.getFullYear(), quarterMonth, 1)
      end = new Date(now.getFullYear(), quarterMonth + 3, 0, 23, 59, 59, 999)
      break
    case 'custom':
      // Custom range
      if (customStartDate.value && customEndDate.value) {
        start = new Date(customStartDate.value)
        start.setHours(0, 0, 0, 0)
        end = new Date(customEndDate.value)
        end.setHours(23, 59, 59, 999)
      } else {
        // Fallback to current month (use actual current date)
        const year = now.getFullYear()
        const month = now.getMonth()
        start = new Date(year, month, 1)
        end = new Date(year, month + 1, 0, 23, 59, 59, 999)
      }
      break
    default:
      // Default to current month
      const defaultYear = currentMonth.value.getFullYear()
      const defaultMonth = currentMonth.value.getMonth()
      start = new Date(defaultYear, defaultMonth, 1)
      end = new Date(defaultYear, defaultMonth + 1, 0, 23, 59, 59, 999)
  }

  return {
    start: start.toISOString(),
    end: end.toISOString()
  }
}

// Get month range for current month (kept for calendar view)
const getMonthRange = () => {
  const year = currentMonth.value.getFullYear()
  const month = currentMonth.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0, 23, 59, 59, 999)

  return {
    start: firstDay.toISOString(),
    end: lastDay.toISOString()
  }
}

// Get week range for current week (for calendar week view)
const getWeekRange = () => {
  const weekRange = getWeekRangeForDate(currentMonth.value)
  return {
    start: weekRange.start.toISOString(),
    end: weekRange.end.toISOString()
  }
}

// Get calendar range based on view mode
const getCalendarRange = () => {
  if (calendarViewMode.value === 'week') {
    return getWeekRange()
  } else {
    return getMonthRange()
  }
}

const loadTodos = async () => {
  loading.value = true
  try {
    // Use time range for list view, calendar range for calendar view
    const range =
      viewMode.value === 'list' ? getTimeRange() : getCalendarRange()
    const params = {
      page_size: 1000,
      ordering: '-created_at',
      deadline_after: range.start,
      deadline_before: range.end
    }

    if (filters.value.is_completed !== null) {
      params.is_completed = filters.value.is_completed
    }

    if (filters.value.priority) {
      params.priority = filters.value.priority
    }

    if (filters.value.owner) {
      params.owner = filters.value.owner
    }

    if (filters.value.search) {
      params.search = filters.value.search
    }

    const response = await todosApi.getTodos(params)
    const responseData = response.data.data || response.data
    todos.value =
      responseData.list || responseData.results || responseData.data || []
  } catch (err) {
    console.error('Failed to load todos:', err)
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const response = await todosApi.getTodoStats()
    stats.value = response.data.data || response.data
  } catch (err) {
    console.error('Failed to load stats:', err)
  }
}

const getTodosForDate = (date) => {
  if (!date) return []
  const dateStr = formatDateForComparison(date)
  return todos.value.filter((todo) => {
    if (!todo.deadline) return false
    const todoDate = formatDateForComparison(new Date(todo.deadline))
    return todoDate === dateStr
  })
}

const formatDateForComparison = (date) => {
  if (!date) return ''
  const d = date instanceof Date ? date : new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const formatDate = (date, format) => {
  if (!date) return ''
  return formatDateUtil(
    date instanceof Date ? date.toISOString() : date,
    preferencesStore.currentTimezone,
    format,
    locale.value
  )
}

const formatSelectedDate = (date) => {
  const format = locale.value === 'zh-CN' ? 'yyyy年MM月dd日' : 'MMMM dd, yyyy'
  return formatDate(date, format)
}

const isSameDay = (date1, date2) => {
  if (!date1 || !date2) return false
  return (
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
  )
}

const previousMonth = () => {
  const newDate = new Date(currentMonth.value)
  newDate.setMonth(newDate.getMonth() - 1)
  currentMonth.value = newDate
}

const nextMonth = () => {
  const newDate = new Date(currentMonth.value)
  newDate.setMonth(newDate.getMonth() + 1)
  currentMonth.value = newDate
}

const previousPeriod = () => {
  if (calendarViewMode.value === 'week') {
    // Previous week
    const newDate = new Date(currentMonth.value)
    newDate.setDate(newDate.getDate() - 7)
    currentMonth.value = newDate
  } else {
    // Previous month
    previousMonth()
  }
}

const nextPeriod = () => {
  if (calendarViewMode.value === 'week') {
    // Next week
    const newDate = new Date(currentMonth.value)
    newDate.setDate(newDate.getDate() + 7)
    currentMonth.value = newDate
  } else {
    // Next month
    nextMonth()
  }
}

const selectDate = (date) => {
  selectedDate.value = isSameDay(date, selectedDate.value) ? null : date
}

let searchTimeout = null

const debounceLoadTodos = () => {
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  searchTimeout = setTimeout(() => {
    loadTodos()
  }, 300)
}

// Clicking a todo in the calendar narrows the list below to that day.
const handleCalendarTodoClick = (todo, date) => {
  selectedDate.value = date
}

const handleEditTodo = (todo) => {
  // Only show editor modal in list view, not in calendar view
  if (viewMode.value === 'calendar') {
    // In calendar view, select the date and scroll to detail area
    if (todo.deadline) {
      const todoDate = new Date(todo.deadline)
      todoDate.setHours(0, 0, 0, 0)
      handleCalendarTodoClick(todo, todoDate)
    }
  } else {
    // In list view, show editor modal
    editingTodo.value = todo
    showTodoEditor.value = true
  }
}

const closeTodoEditor = () => {
  showTodoEditor.value = false
  editingTodo.value = null
}

const handleSaveTodo = async (todoData) => {
  savingTodo.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    if (editingTodo.value && editingTodo.value.id) {
      await todosApi.updateTodo(editingTodo.value.id, todoData)
      successMessage.value =
        t('todos.updateSuccess') || 'TODO updated successfully'
    } else {
      await todosApi.createTodo(todoData)
      successMessage.value =
        t('todos.createSuccess') || 'TODO created successfully'
    }
    await Promise.all([loadTodos(), loadStats()])
    closeTodoEditor()

    // Auto-hide success message after 3 seconds
    setTimeout(() => {
      successMessage.value = ''
    }, 3000)
  } catch (err) {
    console.error('Failed to save todo:', err)
    errorMessage.value = extractErrorMessage(
      err,
      t('common.error') + ': ' + t('todos.save')
    )
  } finally {
    savingTodo.value = false
  }
}

const handleToggleTodo = async (todoId) => {
  todoLoading.value[todoId] = true
  errorMessage.value = ''
  try {
    const todo = todos.value.find((t) => t.id === todoId)
    if (!todo) return

    await todosApi.updateTodo(todoId, {
      is_completed: !todo.is_completed
    })
    await Promise.all([loadTodos(), loadStats()])
  } catch (err) {
    console.error('Failed to toggle todo:', err)
    errorMessage.value = extractErrorMessage(
      err,
      t('common.error') + ': ' + t('todos.markCompleted')
    )
  } finally {
    todoLoading.value[todoId] = false
  }
}

const handleDeleteTodo = async (todoId) => {
  todoLoading.value[todoId] = true
  errorMessage.value = ''
  try {
    await todosApi.deleteTodo(todoId)
    await Promise.all([loadTodos(), loadStats()])
    if (selectedDate.value) {
      const dateTodos = getTodosForDate(selectedDate.value)
      if (dateTodos.length === 0) {
        selectedDate.value = null
      }
    }
    successMessage.value =
      t('todos.deleteSuccess') || 'TODO deleted successfully'
    setTimeout(() => {
      successMessage.value = ''
    }, 3000)
  } catch (err) {
    console.error('Failed to delete todo:', err)
    errorMessage.value = extractErrorMessage(
      err,
      t('common.error') + ': ' + t('todos.delete')
    )
  } finally {
    todoLoading.value[todoId] = false
  }
}

// Select time range
const selectTimeRange = (range) => {
  timeRange.value = range
  if (range === 'custom') {
    // Initialize custom dates if not set
    if (!customStartDate.value) {
      const today = new Date()
      const firstDay = new Date(today.getFullYear(), today.getMonth(), 1)
      customStartDate.value = firstDay.toISOString().split('T')[0]
    }
    if (!customEndDate.value) {
      const today = new Date()
      const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0)
      customEndDate.value = lastDay.toISOString().split('T')[0]
    }
  }
  loadTodos()
}

// Handle custom date change
const handleCustomDateChange = () => {
  if (timeRange.value === 'custom') {
    // Validate custom date range (max 1 month)
    if (customStartDate.value && customEndDate.value) {
      const start = new Date(customStartDate.value)
      const end = new Date(customEndDate.value)
      const diffTime = Math.abs(end - start)
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

      // Limit to 31 days (1 month)
      if (diffDays > 31) {
        // Adjust end date to be 31 days from start
        const maxEnd = new Date(start)
        maxEnd.setDate(maxEnd.getDate() + 31)
        const year = maxEnd.getFullYear()
        const month = String(maxEnd.getMonth() + 1).padStart(2, '0')
        const day = String(maxEnd.getDate()).padStart(2, '0')
        customEndDate.value = `${year}-${month}-${day}`
      }
    }
    selectTimeRange('custom')
  }
}

// Switching to the week view jumps to the week containing today.
watch(calendarViewMode, () => {
  // When switching to week view, show the week containing today
  if (calendarViewMode.value === 'week') {
    const now = new Date()
    const monday = getMondayOfWeek(now)
    // Set to Monday of the week (not the 1st of the month)
    currentMonth.value = new Date(
      monday.getFullYear(),
      monday.getMonth(),
      monday.getDate()
    )
  } else {
    // Month view: show current month
    const now = new Date()
    currentMonth.value = new Date(now.getFullYear(), now.getMonth(), 1)
  }
})

onMounted(() => {
  loadTodos()
  loadStats()
})

watch(
  () => currentMonth.value,
  () => {
    loadTodos()
  }
)

watch(
  () => viewMode.value,
  () => {
    loadTodos()
  }
)

watch(
  () => timeRange.value,
  () => {
    loadTodos()
  }
)

watch(
  () => calendarViewMode.value,
  () => {
    if (viewMode.value === 'calendar') {
      loadTodos()
    }
  }
)

// Watch filters for real-time filtering
watch(
  () => filters.value,
  () => {
    debounceLoadTodos()
  },
  { deep: true }
)
</script>

<style scoped>
/* Todo list animation */
.todo-list-enter-active,
.todo-list-leave-active {
  transition: all 0.3s ease;
}

.todo-list-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.todo-list-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.todo-list-move {
  transition: transform 0.3s ease;
}

/* Fade transition for loading overlay */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
