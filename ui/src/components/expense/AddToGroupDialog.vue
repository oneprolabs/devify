<template>
  <BaseModal :show="true" @close="$emit('close')">
    <div class="space-y-5">
      <div>
        <h3 class="text-lg font-semibold text-ink">
          {{
            moving
              ? t('expense.groups.moveTitle')
              : t('expense.groups.addTitle')
          }}
        </h3>
        <p class="mt-1 text-sm text-ink-3">
          {{
            moving
              ? t('expense.groups.moveSubtitle', { count })
              : t('expense.groups.addSubtitle', { count })
          }}
        </p>
      </div>

      <p
        v-if="error"
        class="rounded-lg border border-bad bg-bad-soft p-3 text-sm text-bad"
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
              ? 'border-accent bg-accent-soft'
              : 'border-line hover:border-line'
          "
        >
          <input
            v-model="target"
            type="radio"
            :value="group.uuid"
            class="text-accent focus:ring-accent"
          />
          <span class="min-w-0">
            <span class="block truncate text-sm text-ink">
              {{ group.name }}
            </span>
            <span class="block text-xs text-ink-3">
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
              ? 'border-accent bg-accent-soft'
              : 'border-line hover:border-line'
          "
        >
          <input
            v-model="target"
            type="radio"
            :value="NEW"
            class="text-accent focus:ring-accent"
          />
          <span class="flex-1">
            <span class="block text-sm text-ink">
              {{ t('expense.groups.addToNew') }}
            </span>
            <input
              v-model="newName"
              type="text"
              class="mt-2 w-full rounded-lg border border-line px-3 py-2 text-sm focus:border-accent focus:outline-none"
              :placeholder="t('expense.groups.namePlaceholder')"
              @focus="target = NEW"
            />
          </span>
        </label>
      </div>

      <p class="text-xs leading-relaxed text-ink-3">
        {{
          moving
            ? t('expense.groups.moveNote')
            : t('expense.groups.doubleClaimNote')
        }}
      </p>

      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" @click="$emit('close')">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton :disabled="!canConfirm" :loading="saving" @click="confirm">
          {{
            moving
              ? t('expense.groups.moveConfirm')
              : t('expense.groups.addConfirm')
          }}
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
  },
  // Adding refuses an invoice another group already holds, because a
  // double claim cannot be undone. Moving is the deliberate correction,
  // so it detaches the old membership instead of complaining about it.
  mode: {
    type: String,
    default: 'add'
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
const moving = computed(() => props.mode === 'move')

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
    if (moving.value) {
      await expenseApi.moveGroupItems(uuid, props.invoiceUuids)
    } else {
      await expenseApi.addGroupItems(uuid, props.invoiceUuids)
    }
    emit('added')
  } catch (err) {
    error.value = err?.response?.data?.message || t('expense.groups.addFailed')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
