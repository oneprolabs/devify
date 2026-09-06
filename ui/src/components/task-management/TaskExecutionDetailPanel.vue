<template>
  <!-- Overlay -->
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="show"
      @click="handleClose"
      class="fixed inset-0 bg-ink bg-opacity-50 z-40"
    />
  </Transition>

  <!-- Right Panel -->
  <Transition
    enter-active-class="transition-transform duration-300 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-250 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="show"
      class="fixed inset-y-0 right-0 w-full max-w-2xl bg-panel shadow-xl z-50 flex flex-col"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between px-6 py-4 border-b border-line bg-gradient-to-r from-app-sub to-app-sub flex-shrink-0"
      >
        <h2 class="text-lg font-semibold text-ink">
          {{ t('taskManagement.list.details') }}
        </h2>
        <button
          @click="handleClose"
          class="p-1.5 rounded-md text-ink-4 hover:text-ink-2 hover:bg-chip transition-colors"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <!-- Content - Scrollable -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="task" class="p-6 space-y-6">
          <!-- Basic Information -->
          <div>
            <h3 class="text-sm font-semibold text-ink mb-4">
              {{ t('taskManagement.list.basicInfo') }}
            </h3>
            <dl class="grid grid-cols-1 gap-4">
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.taskName') }}
                </dt>
                <dd class="text-sm font-medium text-ink">
                  {{ task.task_name || '-' }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.module') }}
                </dt>
                <dd class="text-sm font-medium text-ink">
                  {{ task.module || '-' }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.status') }}
                </dt>
                <dd>
                  <StatusBadge :status="mapTaskStatus(task.status)" />
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.taskId') }}
                </dt>
                <dd class="text-sm font-medium text-ink font-mono">
                  {{ task.task_id || '-' }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.createdAt') }}
                </dt>
                <dd class="text-sm font-medium text-ink">
                  {{ formatDate(task.created_at) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.startedAt') }}
                </dt>
                <dd class="text-sm font-medium text-ink">
                  {{ formatDate(task.started_at) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.finishedAt') }}
                </dt>
                <dd class="text-sm font-medium text-ink">
                  {{ formatDate(task.finished_at) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.duration') }}
                </dt>
                <dd class="text-sm font-medium text-ink">
                  {{ formatDuration(task.duration) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.createdBy') }}
                </dt>
                <dd class="text-sm font-medium text-ink">
                  {{ task.created_by_username || '-' }}
                </dd>
              </div>
              <div v-if="task.error">
                <dt
                  class="text-xs font-semibold text-bad mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.error') }}
                </dt>
                <dd class="text-sm text-bad whitespace-pre-wrap">
                  {{ task.error }}
                </dd>
              </div>
              <div v-if="task.result !== undefined && task.result !== null">
                <dt
                  class="text-xs font-semibold text-ink-2 mb-2 uppercase tracking-wider"
                >
                  {{ t('taskManagement.list.result') }}
                </dt>
                <dd class="text-sm text-ink-2">
                  <pre
                    class="bg-app-sub p-3 rounded text-xs overflow-auto max-h-64"
                    >{{ JSON.stringify(task.result, null, 2) }}</pre
                  >
                </dd>
              </div>
            </dl>
          </div>

          <!-- Detailed steps / execution logs from metadata -->
          <div class="border-t border-line pt-6">
            <h3 class="text-sm font-semibold text-ink mb-4">
              {{ t('taskManagement.list.detailedSteps') }}
            </h3>
            <div
              v-if="currentProgressText"
              class="mb-4 rounded-lg border border-accent bg-accent-soft p-3 text-sm text-accent"
            >
              <span class="font-medium"
                >{{ t('taskManagement.list.currentProgress') }}:</span
              >
              {{ currentProgressText }}
            </div>
            <div
              v-if="detailSteps.length > 0"
              class="rounded-lg border border-line bg-app-sub shadow-sm overflow-hidden"
            >
              <div class="max-h-96 overflow-y-auto divide-y divide-line">
                <div
                  v-for="(item, index) in detailSteps"
                  :key="index"
                  class="p-4 bg-panel hover:bg-app-sub/80 transition-colors"
                  :class="
                    item.level === 'ERROR'
                      ? 'border-l-4 border-l-red-500'
                      : item.level === 'WARNING'
                        ? 'border-l-4 border-l-amber-500'
                        : ''
                  "
                >
                  <div class="flex items-start gap-3">
                    <span
                      class="flex-shrink-0 w-6 h-6 rounded-full bg-chip text-ink-2 flex items-center justify-center text-xs font-semibold"
                    >
                      {{ index + 1 }}
                    </span>
                    <div class="flex-1 min-w-0">
                      <div class="flex flex-wrap items-center gap-2 mb-1">
                        <span
                          v-if="item.level"
                          class="inline-flex px-2 py-0.5 text-xs font-medium rounded"
                          :class="logLevelClass(item.level)"
                        >
                          {{ item.level }}
                        </span>
                        <span
                          v-if="item.step || item.name"
                          class="text-xs font-semibold text-ink-2"
                        >
                          {{ item.step || item.name }}
                        </span>
                        <span v-if="item.timestamp" class="text-xs text-ink-3">
                          {{ formatStepTime(item.timestamp) }}
                        </span>
                      </div>
                      <p
                        class="text-sm text-ink whitespace-pre-wrap break-words"
                      >
                        {{ item.message }}
                      </p>
                      <pre
                        v-if="item.exception"
                        class="mt-2 text-xs font-mono text-bad whitespace-pre-wrap bg-bad-soft p-2 rounded border border-bad"
                        >{{ item.exception }}</pre
                      >
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <p
              v-else
              class="py-8 text-center text-sm text-ink-3 rounded-lg border border-line bg-app-sub"
            >
              {{ t('taskManagement.list.noStepsOrLogs') }}
            </p>
          </div>

          <!-- Traceback -->
          <div v-if="task.traceback" class="border-t border-line pt-6">
            <h3 class="text-sm font-semibold text-ink mb-4">
              {{ t('taskManagement.list.traceback') }}
            </h3>
            <div class="bg-bad-soft border border-bad rounded-lg p-4 shadow-sm">
              <pre
                class="text-xs font-mono text-bad whitespace-pre-wrap overflow-auto max-h-96"
                >{{ task.traceback }}</pre
              >
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { formatDuration } from '@/utils/formatting'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  task: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close'])

const { t } = useI18n()

const metadata = computed(() => props.task?.metadata || {})

const detailSteps = computed(() => {
  const meta = metadata.value
  if (Array.isArray(meta.steps) && meta.steps.length > 0) {
    return meta.steps.map((s) => ({
      step: s.step ?? s.name,
      name: s.name ?? s.step,
      message: s.message ?? s.description ?? '',
      level: s.level,
      timestamp: s.timestamp ?? s.time
    }))
  }
  if (Array.isArray(meta.logs) && meta.logs.length > 0) {
    return meta.logs.map((log) => ({
      level: log.level,
      message: log.message ?? '',
      timestamp: log.timestamp,
      exception: log.exception
    }))
  }
  if (Array.isArray(meta.task_logs) && meta.task_logs.length > 0) {
    return meta.task_logs.map((log) => ({
      step: log.step ?? log.action,
      name: log.name ?? log.action,
      level: log.level,
      message: log.message ?? '',
      timestamp: log.timestamp,
      exception: log.exception
    }))
  }
  return []
})

const currentProgressText = computed(() => {
  const meta = metadata.value
  const percent = meta.progress_percent
  const msg = meta.progress_message
  const step = meta.progress_step
  if (percent != null && (msg || step)) {
    const parts = []
    if (step) parts.push(step)
    if (msg) parts.push(msg)
    if (percent != null) parts.push(`${percent}%`)
    return parts.join(' · ')
  }
  if (msg) return msg
  if (step) return step
  return ''
})

function formatStepTime(value) {
  if (value == null) return ''
  try {
    const date =
      typeof value === 'number' ? new Date(value * 1000) : new Date(value)
    if (Number.isNaN(date.getTime())) return String(value)
    return format(date, 'yyyy-MM-dd HH:mm:ss')
  } catch {
    return String(value)
  }
}

function logLevelClass(level) {
  const map = {
    ERROR: 'bg-bad-soft text-bad',
    WARNING: 'bg-warn-soft text-warn',
    INFO: 'bg-accent-soft text-accent',
    DEBUG: 'bg-chip text-ink-2',
    CRITICAL: 'bg-bad text-bad'
  }
  return map[level] || 'bg-chip text-ink-2'
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm:ss')
  } catch {
    return dateString
  }
}

const mapTaskStatus = (status) => {
  const m = {
    PENDING: 'pending',
    STARTED: 'processing',
    SUCCESS: 'success',
    FAILURE: 'failed',
    RETRY: 'processing',
    REVOKED: 'failed'
  }
  return m[status] || (status && status.toLowerCase()) || 'pending'
}

const handleClose = () => {
  emit('close')
}
</script>
