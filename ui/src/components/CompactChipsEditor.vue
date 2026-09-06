<template>
  <div class="flex items-center gap-2 flex-wrap">
    <!-- Display Mode -->
    <template v-if="!editing">
      <template v-if="isArray">
        <template v-if="displayChips.length > 0">
          <span
            v-for="(chip, index) in displayChips"
            :key="index"
            class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-md border transition-colors cursor-pointer hover:bg-app-sub"
            :class="chipVariantClasses"
            @click="startEditing"
          >
            {{ chip }}
          </span>
          <span
            v-if="hasMore"
            class="inline-flex items-center px-2 py-0.5 text-xs font-medium text-ink-3 cursor-pointer hover:text-ink-2"
            @click="startEditing"
          >
            +{{ moreCount }}
          </span>
        </template>
        <span
          v-else
          class="inline-flex items-center px-2 py-0.5 text-xs font-medium text-ink-4 cursor-pointer hover:text-ink-2"
          @click="startEditing"
        >
          {{ emptyLabel }}
        </span>
      </template>
      <template v-else>
        <span
          v-if="modelValue && String(modelValue).trim()"
          class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-md border transition-colors cursor-pointer hover:bg-app-sub"
          :class="chipVariantClasses"
          @click="startEditing"
        >
          {{ modelValue }}
        </span>
        <span
          v-else
          class="inline-flex items-center px-2 py-0.5 text-xs font-medium text-ink-4 cursor-pointer hover:text-ink-2"
          @click="startEditing"
        >
          {{ emptyLabel }}
        </span>
      </template>
      <button
        v-if="!disabled"
        @click="startEditing"
        class="inline-flex items-center px-1.5 py-0.5 text-xs text-ink-4 hover:text-ink-2 transition-colors"
        :title="t('common.edit')"
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
            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
          />
        </svg>
      </button>
    </template>

    <!-- Edit Mode -->
    <div v-else class="flex items-center gap-2 flex-wrap">
      <MetadataChipsEditor
        ref="chipsEditorRef"
        :model-value="localValue"
        :disabled="disabled || loading"
        :variant="variant"
        :empty-label="emptyLabel"
        :auto-edit="isValueEmpty && isArray"
        :hide-actions="!isEditingItem"
        :show-add-only="isValueEmpty && isArray"
        @update:modelValue="handleUpdate"
        @change="handleChange"
        @save-request="handleSave"
        @cancel-request="handleCancel"
        @editing-change="
          (editing) => {
            isEditingItem = editing
          }
        "
      />
      <div v-if="showActions" class="flex items-center gap-1">
        <button
          @click="handleSave"
          :disabled="loading"
          class="inline-flex items-center p-1 text-ok hover:bg-ok-soft rounded transition-colors disabled:opacity-50"
          :title="t('common.save')"
        >
          <svg
            v-if="!loading"
            class="w-3.5 h-3.5"
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
          <svg
            v-else
            class="w-3.5 h-3.5 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            ></circle>
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
        </button>
        <button
          @click="handleCancel"
          :disabled="loading"
          class="inline-flex items-center p-1 text-bad hover:bg-bad-soft rounded transition-colors disabled:opacity-50"
          :title="t('common.cancel')"
        >
          <svg
            class="w-3.5 h-3.5"
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
      <!-- Show only cancel button when there are no chips and no changes, but NOT when editing an item -->
      <div v-else-if="!isEditingItem" class="flex items-center gap-1">
        <button
          @click="handleCancel"
          :disabled="loading"
          class="inline-flex items-center p-1 text-ink-4 hover:text-ink-2 hover:bg-chip rounded transition-colors disabled:opacity-50"
          :title="t('common.cancel')"
        >
          <svg
            class="w-3.5 h-3.5"
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
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import MetadataChipsEditor from '@/components/MetadataChipsEditor.vue'

const props = defineProps({
  modelValue: {
    type: [Array, String, Number, Boolean, null],
    default: ''
  },
  variant: {
    type: String,
    default: 'gray'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  emptyLabel: {
    type: String,
    default: '-'
  },
  maxDisplay: {
    type: Number,
    default: 3
  }
})

const emit = defineEmits(['update:modelValue', 'save', 'cancel'])

const { t } = useI18n()

const editing = ref(false)
const localValue = ref(null)
const chipsEditorRef = ref(null)
const isEditingItem = ref(false)

watch(
  () => props.modelValue,
  (newValue) => {
    if (!editing.value) {
      localValue.value = newValue
    }
  },
  { immediate: true }
)

const isArray = computed(() => Array.isArray(props.modelValue))
const chips = computed(() =>
  Array.isArray(props.modelValue) ? props.modelValue : []
)

const displayChips = computed(() => {
  if (!isArray.value) return []
  return chips.value.slice(0, props.maxDisplay)
})

const hasMore = computed(() => {
  if (!isArray.value) return false
  return chips.value.length > props.maxDisplay
})

const moreCount = computed(() => {
  if (!isArray.value) return 0
  return chips.value.length - props.maxDisplay
})

const isValueEmpty = computed(() => {
  if (isArray.value) {
    return !Array.isArray(props.modelValue) || props.modelValue.length === 0
  }
  return (
    props.modelValue === null ||
    props.modelValue === undefined ||
    props.modelValue === ''
  )
})

const showActions = computed(() => {
  // Hide external actions when editing an item (use internal actions instead)
  if (isEditingItem.value) return false

  // Always show actions for non-array values
  if (!isArray.value) return true

  // For arrays:
  // If we have local items, show actions (so we can save)
  if (localValue.value && localValue.value.length > 0) return true

  // If we have NO local items:
  // Only hide actions if the original value was ALSO empty (clean start)
  // If original value had items and we deleted them all, we must show Save to allow saving the empty state
  if (!props.modelValue || props.modelValue.length === 0) return false

  return true
})

const chipVariantClasses = computed(() => {
  const variants = {
    blue: 'bg-accent-soft text-accent border-accent',
    green: 'bg-ok-soft text-ok border-ok',
    purple: 'bg-accent-soft text-accent border-accent',
    rose: 'bg-bad-soft text-bad border-bad',
    gray: 'bg-app-sub text-ink-2 border-line'
  }
  return variants[props.variant] || variants.gray
})

const startEditing = () => {
  if (props.disabled) return
  // If value is empty, ensure we have the right type for editing
  if (isArray.value) {
    localValue.value =
      Array.isArray(props.modelValue) && props.modelValue.length > 0
        ? [...props.modelValue]
        : []
  } else {
    localValue.value = props.modelValue || ''
  }
  editing.value = true
  // Don't auto-start editing - let user click on chips or add button to edit
}

const handleUpdate = (value) => {
  localValue.value = value
}

const handleChange = (value) => {
  localValue.value = value
  emit('update:modelValue', value)
}

const handleSave = async () => {
  // Ensure we have the latest value before saving
  await nextTick()
  emit('update:modelValue', localValue.value)
  emit('save', localValue.value)
}

const handleCancel = () => {
  localValue.value = props.modelValue
  editing.value = false
  emit('cancel')
}

watch(
  () => props.loading,
  (newValue) => {
    if (!newValue && editing.value) {
      editing.value = false
    }
  }
)

watch(
  () => props.modelValue,
  () => {
    if (!editing.value) {
      localValue.value = props.modelValue
    }
  }
)
</script>
