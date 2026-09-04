<template>
  <div
    :class="[
      'group relative flex gap-[11px] border-b border-line-soft px-4 py-3 transition-colors last:border-b-0',
      shouldAlignTop ? 'items-start' : 'items-start',
      isAnyEditing ? 'bg-accent-soft' : ''
    ]"
  >
    <div
      v-if="!readOnly"
      class="flex-shrink-0"
      :class="shouldAlignTop ? 'pt-0.5' : ''"
    >
      <input
        type="checkbox"
        :checked="todo.is_completed"
        @change="handleToggle"
        :disabled="loading || isAnyEditing"
        class="h-4 w-4 rounded-sm border-line text-ok focus:ring-accent"
      />
    </div>

    <div class="flex-1 min-w-0">
      <!-- Edit Mode -->
      <div v-if="editing" class="space-y-4 sm:space-y-3">
        <!-- Validation Error -->
        <div
          v-if="validationError"
          class="rounded-md bg-bad-soft border border-bad p-2"
        >
          <p class="text-xs font-medium text-bad">{{ validationError }}</p>
        </div>

        <!-- Content -->
        <div>
          <label class="block text-xs font-medium text-ink-2 mb-1">
            {{ t('todos.content') }} <span class="text-bad">*</span>
          </label>
          <textarea
            v-model="editForm.content"
            rows="2"
            class="w-full px-2 py-1.5 text-sm border border-line rounded-md shadow-sm focus:ring-accent focus:border-accent"
            :class="{ 'border-bad': validationError }"
            :placeholder="t('todos.content')"
          ></textarea>
        </div>

        <!-- Fields Grid -->
        <div class="grid grid-cols-2 gap-2">
          <!-- Priority -->
          <div>
            <label class="block text-xs font-medium text-ink-2 mb-1">
              {{ t('todos.priority.label') }}
            </label>
            <select
              v-model="editForm.priority"
              class="w-full px-2 py-1.5 text-sm border border-line rounded-md shadow-sm focus:ring-accent focus:border-accent"
            >
              <option :value="null">{{ t('todos.notSet') }}</option>
              <option value="high">{{ t('todos.priority.high') }}</option>
              <option value="medium">{{ t('todos.priority.medium') }}</option>
              <option value="low">{{ t('todos.priority.low') }}</option>
            </select>
          </div>

          <!-- Owner -->
          <div>
            <label class="block text-xs font-medium text-ink-2 mb-1">
              {{ t('todos.owner') }}
            </label>
            <input
              v-model="editForm.owner"
              type="text"
              class="w-full px-2 py-1.5 text-sm border border-line rounded-md shadow-sm focus:ring-accent focus:border-accent"
              :placeholder="t('todos.owner')"
            />
          </div>

          <!-- Deadline -->
          <div>
            <label class="block text-xs font-medium text-ink-2 mb-1">
              {{ t('todos.deadline') }}
            </label>
            <BaseDateTimePicker
              v-model="editForm.deadline"
              :placeholder="t('todos.deadline')"
            />
          </div>

          <!-- Location -->
          <div>
            <label class="block text-xs font-medium text-ink-2 mb-1">
              {{ t('todos.location') }}
            </label>
            <input
              v-model="editForm.location"
              type="text"
              class="w-full px-2 py-1.5 text-sm border border-line rounded-md shadow-sm focus:ring-accent focus:border-accent"
              :placeholder="t('todos.location')"
            />
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex items-center justify-end gap-2 pt-1">
          <button
            @click="handleCancelEdit"
            :disabled="saving"
            class="px-3 py-1.5 text-xs font-medium text-ink-2 bg-panel border border-line rounded-md hover:bg-app-sub focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent disabled:opacity-50"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="handleSaveEdit"
            :disabled="saving || !editForm.content || !editForm.content.trim()"
            class="px-3 py-1.5 text-xs font-medium text-accent-on bg-accent border border-transparent rounded-md hover:bg-accent focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="saving">{{ t('common.saving') }}...</span>
            <span v-else>{{ t('common.save') }}</span>
          </button>
        </div>
      </div>

      <!-- View Mode -->
      <div v-else>
        <!-- Content Inline Edit -->
        <div v-if="editingContent" class="flex items-center gap-1">
          <input
            v-model="contentInput"
            type="text"
            class="flex-1 text-sm px-2 py-1 border border-accent rounded-md focus:ring-accent focus:border-accent"
            :class="todo.is_completed ? 'bg-app-sub' : 'bg-panel'"
            @keydown.enter.prevent="handleSaveContent"
            @keydown.esc.prevent="handleCancelContentEdit"
            autofocus
          />
          <button
            @mousedown.prevent="handleSaveContent"
            class="p-1 text-ok hover:text-ok"
            :disabled="saving"
            :title="t('common.save')"
          >
            <svg
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M5 13l4 4L19 7"
              ></path>
            </svg>
          </button>
          <button
            @mousedown.prevent="handleCancelContentEdit"
            class="p-1 text-bad hover:text-bad"
            :disabled="saving"
            :title="t('common.cancel')"
          >
            <svg
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              ></path>
            </svg>
          </button>
        </div>
        <div
          v-else
          :class="[
            'select-text text-[13px] leading-[1.5] transition-colors',
            todo.is_completed
              ? 'text-ink-3 line-through cursor-not-allowed'
              : readOnly
                ? 'text-ink cursor-default'
                : 'text-ink hover:opacity-80 cursor-pointer'
          ]"
          @click.stop="readOnly ? null : handleStartContentEdit()"
          :title="readOnly || todo.is_completed ? '' : t('todos.edit')"
        >
          {{ todo.content }}
        </div>

        <div
          v-if="showDetails"
          class="mt-[5px] flex flex-wrap items-center gap-2 font-mono text-[10.5px] text-ink-4 [&>*:not(:first-child)]:before:mr-2 [&>*:not(:first-child)]:before:content-['·']"
        >
          <!-- Priority Inline Edit -->
          <div
            v-if="editingPriority"
            class="flex items-center gap-1 self-center"
          >
            <select
              v-model="priorityInput"
              class="text-xs px-2 py-0.5 h-5 border border-accent rounded-md focus:ring-accent focus:border-accent"
              @keydown.enter.prevent="handleSavePriority"
              @keydown.esc.prevent="handleCancelPriorityEdit"
              autofocus
            >
              <option :value="null">{{ t('common.noData') }}</option>
              <option value="high">{{ t('todos.priority.high') }}</option>
              <option value="medium">{{ t('todos.priority.medium') }}</option>
              <option value="low">{{ t('todos.priority.low') }}</option>
            </select>
            <button
              @mousedown.prevent="handleSavePriority"
              class="p-0.5 text-ok hover:text-ok"
              :title="t('common.save')"
            >
              <svg
                class="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M5 13l4 4L19 7"
                ></path>
              </svg>
            </button>
            <button
              @mousedown.prevent="handleCancelPriorityEdit"
              class="p-0.5 text-bad hover:text-bad"
              :title="t('common.cancel')"
            >
              <svg
                class="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                ></path>
              </svg>
            </button>
          </div>
          <span
            v-else-if="todo.priority"
            :class="[
              getPriorityClass(todo.priority),
              'self-center',
              todo.is_completed
                ? 'cursor-not-allowed opacity-60'
                : readOnly
                  ? 'cursor-default'
                  : 'cursor-pointer hover:opacity-80'
            ]"
            @click.stop="readOnly ? null : handleStartPriorityEdit()"
            :title="readOnly || todo.is_completed ? '' : t('todos.edit')"
          >
            {{ t(`todos.priorityShort.${todo.priority}`) }}
          </span>
          <span
            v-else-if="!readOnly"
            :class="[
              'hidden self-center italic text-ink-4 group-hover:inline',
              todo.is_completed
                ? 'cursor-not-allowed opacity-60'
                : readOnly
                  ? 'cursor-default'
                  : 'cursor-pointer hover:opacity-80'
            ]"
            @click.stop="readOnly ? null : handleStartPriorityEdit()"
            :title="readOnly || todo.is_completed ? '' : t('todos.addPriority')"
          >
            + {{ t('todos.priority.label') }}
          </span>

          <!-- Owner Inline Edit -->
          <div v-if="editingOwner" class="flex items-center gap-1 self-center">
            <svg
              class="w-3 h-3 text-ink-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
            <input
              v-model="ownerInput"
              type="text"
              class="text-xs px-2 py-0.5 h-5 border border-accent rounded-md focus:ring-accent focus:border-accent w-24"
              @keydown.enter.prevent="handleSaveOwner"
              @keydown.esc.prevent="handleCancelOwnerEdit"
              autofocus
            />
            <button
              @mousedown.prevent="handleSaveOwner"
              class="p-0.5 text-ok hover:text-ok"
              :title="t('common.save')"
            >
              <svg
                class="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M5 13l4 4L19 7"
                ></path>
              </svg>
            </button>
            <button
              @mousedown.prevent="handleCancelOwnerEdit"
              class="p-0.5 text-bad hover:text-bad"
              :title="t('common.cancel')"
            >
              <svg
                class="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                ></path>
              </svg>
            </button>
          </div>
          <span
            v-else-if="todo.owner"
            :class="[
              'flex items-center gap-1 self-center',
              todo.is_completed
                ? 'cursor-not-allowed opacity-60'
                : readOnly
                  ? 'cursor-default'
                  : 'cursor-pointer hover:opacity-80'
            ]"
            @click.stop="readOnly ? null : handleStartOwnerEdit()"
            :title="readOnly || todo.is_completed ? '' : t('todos.edit')"
          >
            {{ todo.owner }}
          </span>
          <span
            v-else-if="!readOnly"
            :class="[
              'hidden items-center gap-1 self-center italic text-ink-4 group-hover:flex',
              todo.is_completed
                ? 'cursor-not-allowed opacity-60'
                : 'cursor-pointer hover:opacity-80'
            ]"
            @click.stop="handleStartOwnerEdit"
            :title="todo.is_completed ? '' : t('todos.addOwner')"
          >
            <svg
              class="w-3 h-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
            + {{ t('todos.owner') }}
          </span>

          <!-- Deadline Inline Edit -->
          <div
            v-if="editingDeadline"
            class="flex items-center gap-1 self-center"
          >
            <div class="w-48 min-w-[12rem] flex items-center gap-1">
              <svg
                class="w-3 h-3 text-ink-3 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <BaseDateTimePicker
                v-model="deadlineInput"
                :placeholder="t('todos.deadline')"
                size="compact"
                :show-input-icon="false"
              />
            </div>
            <button
              @mousedown.prevent="handleSaveDeadline"
              class="p-0.5 text-ok hover:text-ok"
              :title="t('common.save')"
            >
              <svg
                class="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M5 13l4 4L19 7"
                ></path>
              </svg>
            </button>
            <button
              @mousedown.prevent="handleCancelDeadlineEdit"
              class="p-0.5 text-bad hover:text-bad"
              :title="t('common.cancel')"
            >
              <svg
                class="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                ></path>
              </svg>
            </button>
          </div>
          <span
            v-else-if="todo.deadline"
            :class="[
              'flex items-center gap-1 self-center',
              todo.is_completed
                ? 'cursor-not-allowed opacity-60'
                : readOnly
                  ? 'cursor-default'
                  : 'cursor-pointer hover:opacity-80'
            ]"
            @click.stop="readOnly ? null : handleStartDeadlineEdit()"
            :title="readOnly || todo.is_completed ? '' : t('todos.edit')"
          >
            {{ formatDeadline(todo.deadline) }}
            <span v-if="deadlineStatusText" :class="deadlineToneClass">
              · {{ deadlineStatusText }}
            </span>
          </span>
          <span
            v-else-if="!readOnly"
            :class="[
              'hidden items-center gap-1 self-center italic text-ink-4 group-hover:flex',
              todo.is_completed
                ? 'cursor-not-allowed opacity-60'
                : readOnly
                  ? 'cursor-default'
                  : 'cursor-pointer hover:opacity-80'
            ]"
            @click.stop="readOnly ? null : handleStartDeadlineEdit()"
            :title="readOnly || todo.is_completed ? '' : t('todos.addDeadline')"
          >
            <svg
              class="w-3 h-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            + {{ t('todos.deadline') }}
          </span>

          <!-- Location Inline Edit -->
          <div
            v-if="editingLocation"
            class="flex items-center gap-1 self-center"
          >
            <svg
              class="w-3 h-3 text-ink-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
              />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            <input
              v-model="locationInput"
              type="text"
              class="text-xs px-2 py-0.5 h-5 border border-accent rounded-md focus:ring-accent focus:border-accent w-24"
              @keydown.enter.prevent="handleSaveLocation"
              @keydown.esc.prevent="handleCancelLocationEdit"
              autofocus
            />
            <button
              @mousedown.prevent="handleSaveLocation"
              class="p-0.5 text-ok hover:text-ok"
              :title="t('common.save')"
            >
              <svg
                class="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M5 13l4 4L19 7"
                ></path>
              </svg>
            </button>
            <button
              @mousedown.prevent="handleCancelLocationEdit"
              class="p-0.5 text-bad hover:text-bad"
              :title="t('common.cancel')"
            >
              <svg
                class="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                ></path>
              </svg>
            </button>
          </div>
          <span
            v-else-if="todo.location"
            :class="[
              'flex items-center gap-1 self-center',
              todo.is_completed
                ? 'cursor-not-allowed opacity-60'
                : readOnly
                  ? 'cursor-default'
                  : 'cursor-pointer hover:opacity-80'
            ]"
            @click.stop="readOnly ? null : handleStartLocationEdit()"
            :title="readOnly || todo.is_completed ? '' : t('todos.edit')"
          >
            <svg
              class="w-3 h-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
              />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            {{ todo.location }}
          </span>
          <span
            v-else-if="!readOnly"
            :class="[
              'hidden items-center gap-1 self-center italic text-ink-4 group-hover:flex',
              todo.is_completed
                ? 'cursor-not-allowed opacity-60'
                : readOnly
                  ? 'cursor-default'
                  : 'cursor-pointer hover:opacity-80'
            ]"
            @click.stop="readOnly ? null : handleStartLocationEdit()"
            :title="readOnly || todo.is_completed ? '' : t('todos.addLocation')"
          >
            <svg
              class="w-3 h-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
              />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            + {{ t('todos.location') }}
          </span>
        </div>
      </div>
    </div>

    <div
      class="flex-shrink-0 flex gap-1 items-center"
      :class="shouldAlignTop ? 'items-start pt-0.5' : 'items-center'"
    >
      <template v-if="!isAnyEditing">
        <!-- Deadline Status Badge -->
        <button
          v-if="!confirmingDelete && !isNew && !readOnly"
          @click="handleDeleteClick"
          :disabled="loading"
          class="p-1 text-ink-4 opacity-0 transition-opacity hover:text-bad group-hover:opacity-100"
          :title="t('todos.delete')"
        >
          <svg
            class="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </button>
        <div v-else-if="!readOnly" class="flex items-center gap-1">
          <button
            class="p-1 text-ok hover:text-ok focus:outline-none"
            @click="confirmDelete"
            :aria-label="t('todos.delete')"
          >
            <svg
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M5 13l4 4L19 7"
              />
            </svg>
          </button>
          <button
            class="p-1 text-ink-3 hover:text-ink-2 focus:outline-none"
            @click="cancelDelete"
            :aria-label="t('common.cancel')"
          >
            <svg
              class="w-4 h-4"
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
      </template>
    </div>

    <div
      v-if="loading"
      class="absolute inset-0 flex items-center justify-center z-20 pointer-events-none"
    >
      <div
        class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-accent bg-panel/80 rounded-full px-1 py-1"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseDateTimePicker from '@/components/ui/BaseDateTimePicker.vue'
import { usePreferencesStore } from '@/store/preferences'
import { formatDate as formatDateUtil } from '@/utils/timezone'

const props = defineProps({
  todo: {
    type: Object,
    required: true
  },
  showDetails: {
    type: Boolean,
    default: true
  },
  loading: {
    type: Boolean,
    default: false
  },
  emailMessageId: {
    type: Number,
    default: null
  },
  isNew: {
    type: Boolean,
    default: false
  },
  autoEdit: {
    type: Boolean,
    default: false
  },
  readOnly: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'toggle',
  'save',
  'delete',
  'cancel-new',
  'editing-change'
])

const { t, locale } = useI18n()
const preferencesStore = usePreferencesStore()

const editing = ref(false)
const editingContent = ref(false)
const editingPriority = ref(false)
const editingOwner = ref(false)
const editingDeadline = ref(false)
const editingLocation = ref(false)
const contentInput = ref('')
const priorityInput = ref(null)
const ownerInput = ref('')
const deadlineInput = ref(null)
const locationInput = ref('')
const saving = ref(false)
const validationError = ref('')
const confirmingDelete = ref(false)
const editForm = ref({
  content: '',
  priority: null,
  owner: '',
  deadline: null,
  location: ''
})

// Watch for isNew prop to enter inline content edit mode automatically
watch(
  () => props.isNew,
  (isNew) => {
    if (isNew) {
      // Don't enter full edit mode, but inline content edit mode
      editing.value = false
      editingContent.value = true
      contentInput.value = props.todo.content || ''
    }
  },
  { immediate: true }
)

// Watch for autoEdit prop to enter edit mode automatically
watch(
  () => props.autoEdit,
  (autoEdit) => {
    if (autoEdit) {
      editing.value = true
      nextTick(() => {
        resetEditForm()
      })
    }
  },
  { immediate: true }
)

const isInlineEditing = computed(
  () =>
    editingContent.value ||
    editingPriority.value ||
    editingOwner.value ||
    editingDeadline.value ||
    editingLocation.value
)
const isAnyEditing = computed(() => editing.value || isInlineEditing.value)
const shouldAlignTop = computed(() => editing.value)
const isEditingLocked = computed(() => Boolean(props.todo?.is_completed))

const resetEditForm = () => {
  editForm.value = {
    content: props.todo.content || '',
    priority: props.todo.priority || null,
    owner: props.todo.owner || '',
    deadline: props.todo.deadline || null,
    location: props.todo.location || ''
  }
  validationError.value = ''
}

// Watch todo changes to reset edit form
watch(
  () => props.todo,
  (newTodo) => {
    if (newTodo && !editing.value) {
      resetEditForm()
    }
  },
  { immediate: true, deep: true }
)

const getPriorityClass = (priority) => {
  const classes = {
    high: 'rounded-sm bg-bad-soft px-1.5 py-0.5 font-mono text-[10px] text-bad',
    medium:
      'rounded-sm bg-warn-soft px-1.5 py-0.5 font-mono text-[10px] text-warn',
    low: 'rounded-sm bg-chip px-1.5 py-0.5 font-mono text-[10px] text-ink-3'
  }
  return (
    classes[priority] ||
    'rounded-sm bg-chip px-1.5 py-0.5 font-mono text-[10px] text-ink-3'
  )
}

const formatDeadline = (dateString) => {
  if (!dateString) return ''
  const currentLang = locale.value || preferencesStore.currentLanguage || 'en'
  const zone = preferencesStore.currentTimezone
  const clock = formatDateUtil(dateString, zone, 'HH:mm', currentLang)
  const day = formatDateUtil(dateString, zone, 'MM-dd', currentLang)
  // Midnight means "that day", not "that minute", so the clock is noise.
  return clock === '00:00' ? day : `${day} ${clock}`
}

// Deadline status computation
const deadlineStatus = computed(() => {
  if (!props.todo.deadline || props.todo.is_completed) return null

  const deadline = new Date(props.todo.deadline)
  const now = new Date()
  const diffMs = deadline - now
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 0) {
    // Past due
    return 'overdue'
  } else if (diffDays === 0) {
    // Due today
    return 'due-today'
  } else if (diffDays <= 3) {
    // Due soon (within 3 days)
    return 'due-soon'
  }

  return null
})

const deadlineDaysAway = computed(() => {
  if (!props.todo.deadline || props.todo.is_completed) return null
  const diffMs = new Date(props.todo.deadline) - new Date()
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24))
})

const deadlineStatusText = computed(() => {
  const days = deadlineDaysAway.value
  if (days === null) return ''
  if (days < 0) return t('todos.overdueBy', { days: Math.abs(days) })
  if (days === 0) return t('todos.dueTodayShort')
  if (days <= 3) return t('todos.dueIn', { days })
  return ''
})

const deadlineToneClass = computed(() =>
  deadlineStatus.value === 'overdue' ? 'text-bad' : 'text-warn'
)

const handleToggle = () => {
  if (!editing.value) {
    emit('toggle', props.todo.id)
  }
}

/* eslint-disable-next-line no-unused-vars */
const handleStartEdit = () => {
  if (isEditingLocked.value) return
  resetEditForm()
  editing.value = true
}

const handleCancelEdit = () => {
  if (props.isNew) {
    // If this is a new todo, emit cancel-new event
    emit('cancel-new')
    return
  }
  editing.value = false
  validationError.value = ''
  resetEditForm()
}

const handleStartContentEdit = () => {
  if (isEditingLocked.value) return
  if (editing.value || editingContent.value) return
  contentInput.value = props.todo.content || ''
  editingContent.value = true
}

// Auto-start content edit for new todos
if (props.isNew) {
  editingContent.value = true
  contentInput.value = props.todo.content || ''
}

const handleCancelContentEdit = () => {
  if (props.isNew) {
    // If this is a new todo, emit cancel-new event
    emit('cancel-new')
    return
  }
  editingContent.value = false
  contentInput.value = ''
}

const handleSaveContent = async () => {
  const trimmedContent = contentInput.value.trim()
  if (!trimmedContent) {
    validationError.value =
      t('todos.content') + ' ' + (t('common.required') || '必填')
    return
  }

  saving.value = true
  try {
    const todoData = {
      content: trimmedContent,
      priority: props.todo.priority || null,
      owner: props.todo.owner || null,
      deadline: props.todo.deadline || null,
      location: props.todo.location || null
    }

    // Ensure email_message_id is set if provided
    if (props.emailMessageId && !todoData.email_message_id) {
      todoData.email_message_id = props.emailMessageId
    }

    // Emit save event - parent component should handle the API call
    const savePromise = emit('save', props.todo.id, todoData)
    if (savePromise && typeof savePromise.then === 'function') {
      await savePromise
    }

    // Exit content edit mode after saving
    editingContent.value = false

    // For new todos, the parent component will handle the creation
    // and update the todo object, so the content will be displayed
  } catch (err) {
    validationError.value = err.message || t('common.error')
  } finally {
    saving.value = false
  }
}

const handleStartPriorityEdit = () => {
  if (isEditingLocked.value) return
  if (
    editing.value ||
    editingContent.value ||
    editingOwner.value ||
    editingDeadline.value ||
    editingLocation.value
  )
    return
  priorityInput.value = props.todo.priority || null
  editingPriority.value = true
}

const handleCancelPriorityEdit = () => {
  editingPriority.value = false
  priorityInput.value = null
}

const handleSavePriority = async () => {
  saving.value = true
  try {
    const todoData = {
      content: props.todo.content || '',
      priority: priorityInput.value,
      owner: props.todo.owner || null,
      deadline: props.todo.deadline || null,
      location: props.todo.location || null
    }

    if (props.emailMessageId && !todoData.email_message_id) {
      todoData.email_message_id = props.emailMessageId
    }

    const savePromise = emit('save', props.todo.id, todoData)
    if (savePromise && typeof savePromise.then === 'function') {
      await savePromise
    }
    editingPriority.value = false
  } catch (err) {
    validationError.value = err.message || t('common.error')
  } finally {
    saving.value = false
  }
}

const handleStartOwnerEdit = () => {
  if (isEditingLocked.value) return
  if (
    editing.value ||
    editingContent.value ||
    editingPriority.value ||
    editingDeadline.value ||
    editingLocation.value
  )
    return
  ownerInput.value = props.todo.owner || ''
  editingOwner.value = true
}

const handleCancelOwnerEdit = () => {
  editingOwner.value = false
  ownerInput.value = ''
}

const handleSaveOwner = async () => {
  saving.value = true
  try {
    const todoData = {
      content: props.todo.content || '',
      priority: props.todo.priority || null,
      owner: ownerInput.value.trim() || null,
      deadline: props.todo.deadline || null,
      location: props.todo.location || null
    }

    if (props.emailMessageId && !todoData.email_message_id) {
      todoData.email_message_id = props.emailMessageId
    }

    const savePromise = emit('save', props.todo.id, todoData)
    if (savePromise && typeof savePromise.then === 'function') {
      await savePromise
    }
    editingOwner.value = false
  } catch (err) {
    validationError.value = err.message || t('common.error')
  } finally {
    saving.value = false
  }
}

const handleStartDeadlineEdit = () => {
  if (isEditingLocked.value) return
  if (
    editing.value ||
    editingContent.value ||
    editingPriority.value ||
    editingOwner.value ||
    editingLocation.value
  )
    return
  deadlineInput.value = props.todo?.deadline || null
  editingDeadline.value = true
}

const handleCancelDeadlineEdit = () => {
  editingDeadline.value = false
  deadlineInput.value = props.todo?.deadline || null
}

const handleSaveDeadline = async () => {
  saving.value = true
  try {
    const todoData = {
      content: props.todo.content || '',
      priority: props.todo.priority || null,
      owner: props.todo.owner || null,
      deadline: deadlineInput.value
        ? new Date(deadlineInput.value).toISOString()
        : null,
      location: props.todo.location || null
    }

    if (props.emailMessageId && !todoData.email_message_id) {
      todoData.email_message_id =
        props.todo.email_message_id ?? props.email_message_id ?? null
    }

    const savePromise = emit('save', props.todo.id, todoData)
    if (savePromise && typeof savePromise.then === 'function') {
      await savePromise
    }
    editingDeadline.value = false
  } catch (err) {
    validationError.value = err.message || t('common.error')
  } finally {
    saving.value = false
  }
}

const handleStartLocationEdit = () => {
  if (isEditingLocked.value) return
  if (
    editing.value ||
    editingContent.value ||
    editingPriority.value ||
    editingOwner.value ||
    editingDeadline.value
  )
    return
  locationInput.value = props.todo.location || ''
  editingLocation.value = true
}

const handleCancelLocationEdit = () => {
  editingLocation.value = false
  locationInput.value = ''
}

const handleSaveLocation = async () => {
  saving.value = true
  try {
    const todoData = {
      content: props.todo.content || '',
      priority: props.todo.priority || null,
      owner: props.todo.owner || null,
      deadline: props.todo.deadline || null,
      location: locationInput.value.trim() || null
    }

    if (props.emailMessageId && !todoData.email_message_id) {
      todoData.email_message_id = props.emailMessageId
    }

    const savePromise = emit('save', props.todo.id, todoData)
    if (savePromise && typeof savePromise.then === 'function') {
      await savePromise
    }
    editingLocation.value = false
  } catch (err) {
    validationError.value = err.message || t('common.error')
  } finally {
    saving.value = false
  }
}

const handleDeleteClick = () => {
  confirmingDelete.value = true
}

const confirmDelete = () => {
  confirmingDelete.value = false
  emit('delete', props.todo.id)
}

const cancelDelete = () => {
  confirmingDelete.value = false
}

const handleSaveEdit = async () => {
  validationError.value = ''

  // Validate - content is required
  if (!editForm.value.content || !editForm.value.content.trim()) {
    validationError.value =
      t('todos.content') + ' ' + (t('common.required') || '必填')
    return
  }

  saving.value = true
  try {
    const todoData = {
      content: editForm.value.content.trim(),
      priority: editForm.value.priority || null,
      owner: editForm.value.owner.trim() || null,
      deadline: editForm.value.deadline || null,
      location: editForm.value.location.trim() || null
    }

    // Ensure email_message_id is set if provided
    if (props.emailMessageId && !todoData.email_message_id) {
      todoData.email_message_id = props.emailMessageId
    }

    // Emit save event - parent component should handle the API call
    const savePromise = emit('save', props.todo.id, todoData)
    if (savePromise && typeof savePromise.then === 'function') {
      await savePromise
    }
    editing.value = false
  } catch (err) {
    validationError.value = err.message || t('common.error')
  } finally {
    saving.value = false
  }
}

// Track previous editing state to avoid unnecessary emits
const previousEditingState = ref(false)
const isMounted = ref(false)

watch(
  isAnyEditing,
  (val) => {
    if (val) {
      confirmingDelete.value = false
    }
    // Only emit if component is mounted and state actually changed
    if (isMounted.value && val !== previousEditingState.value) {
      previousEditingState.value = val
      emit('editing-change', val)
    }
  },
  { immediate: false }
)

// Initialize when component is created
onMounted(() => {
  if (props.isNew) {
    // Enter inline content edit mode for new todos
    editing.value = false
    editingContent.value = true
    contentInput.value = props.todo.content || ''
  } else if (props.autoEdit) {
    editing.value = true
    resetEditForm()
  }

  // Mark as mounted and emit initial editing state
  nextTick(() => {
    isMounted.value = true
    previousEditingState.value = isAnyEditing.value
    emit('editing-change', isAnyEditing.value)
  })
})
</script>
