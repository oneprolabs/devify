<template>
  <BaseModal :show="true" @close="$emit('close')">
    <div class="space-y-5">
      <div>
        <h3 class="text-lg font-semibold text-gray-900">
          {{ t('expense.groups.addTitle') }}
        </h3>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('expense.groups.addSubtitle', { count }) }}
        </p>
      </div>

      <p
        v-if="error"
        class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        {{ error }}
      </p>

      <div class="space-y-2">
        <label
          v-for="group in openGroups"
          :key="group.uuid"
          class="flex cursor-pointer items-center gap-3 rounded-lg border p-3"
          :class="
            target === group.uuid
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-200 hover:border-gray-300'
          "
        >
          <input
            v-model="target"
            type="radio"
            :value="group.uuid"
            class="text-primary-600 focus:ring-primary-500"
          />
          <span class="min-w-0">
            <span class="block truncate text-sm text-gray-900">
              {{ group.name }}
            </span>
            <span class="block text-xs text-gray-500">
              {{
                t('expense.groups.line', {
                  count: group.invoice_count,
                  amount: group.total_amount
                })
              }}
            </span>
          </span>
        </label>

        <label
          class="flex cursor-pointer items-center gap-3 rounded-lg border p-3"
          :class="
            target === NEW
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-200 hover:border-gray-300'
          "
        >
          <input
            v-model="target"
            type="radio"
            :value="NEW"
            class="text-primary-600 focus:ring-primary-500"
          />
          <span class="flex-1">
            <span class="block text-sm text-gray-900">
              {{ t('expense.groups.addToNew') }}
            </span>
            <input
              v-model="newName"
              type="text"
              class="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              :placeholder="t('expense.groups.namePlaceholder')"
              @focus="target = NEW"
            />
          </span>
        </label>
      </div>

      <p class="text-xs leading-relaxed text-gray-500">
        {{ t('expense.groups.doubleClaimNote') }}
      </p>

      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" @click="$emit('close')">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton :disabled="!canConfirm" :loading="saving" @click="confirm">
          {{ t('expense.groups.addConfirm') }}
        </BaseButton>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { expenseApi } from '@/api/expense'

const props = defineProps({
  invoiceUuids: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['close', 'added'])

const { t } = useI18n()

const NEW = '__new__'

const groups = ref([])
const target = ref(NEW)
const newName = ref('')
const saving = ref(false)
const error = ref('')

const count = computed(() => props.invoiceUuids.length)

// An archived group is finished; adding to it would reopen a settled
// claim, so only live ones are offered.
const openGroups = computed(() =>
  groups.value.filter((group) => group.status !== 'archived')
)

const canConfirm = computed(() => {
  if (!count.value) return false
  return target.value === NEW ? Boolean(newName.value.trim()) : true
})

async function load() {
  try {
    groups.value = await expenseApi.getGroups()
    if (openGroups.value.length) {
      target.value = openGroups.value[0].uuid
    }
  } catch (err) {
    error.value = err?.response?.data?.message || t('expense.loadFailed')
  }
}

async function confirm() {
  saving.value = true
  error.value = ''
  try {
    let uuid = target.value
    if (uuid === NEW) {
      const created = await expenseApi.createGroup({
        name: newName.value.trim()
      })
      uuid = created.uuid
    }
    await expenseApi.addGroupItems(uuid, props.invoiceUuids)
    emit('added')
  } catch (err) {
    error.value = err?.response?.data?.message || t('expense.groups.addFailed')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
