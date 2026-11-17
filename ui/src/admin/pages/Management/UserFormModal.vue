<template>
  <BaseModal :show="show" :title="title" @close="handleClose">
    <form class="space-y-4" @submit.prevent="handleSubmit">
      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">{{
          t('management.username')
        }}</label>
        <input
          v-model="form.username"
          type="text"
          :disabled="isEdit"
          class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100 disabled:text-gray-500"
          :placeholder="t('management.username')"
        />
        <p v-if="isEdit" class="mt-1 text-xs text-gray-500">
          {{ t('management.usernameImmutable') }}
        </p>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">{{
          t('management.email')
        }}</label>
        <input
          v-model="form.email"
          type="email"
          class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
          :placeholder="t('management.email')"
        />
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">{{
            t('management.firstName')
          }}</label>
          <input
            v-model="form.first_name"
            type="text"
            class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">{{
            t('management.lastName')
          }}</label>
          <input
            v-model="form.last_name"
            type="text"
            class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">{{
          isEdit
            ? t('management.newPasswordOptional')
            : t('password.reset.newPassword')
        }}</label>
        <div class="relative">
          <input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            class="w-full rounded-md border border-gray-300 px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
            :placeholder="
              isEdit
                ? t('management.passwordKeepHint')
                : t('password.reset.newPasswordPlaceholder')
            "
          />
          <button
            type="button"
            class="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded text-gray-500 hover:text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-1 focus:ring-primary-500"
            :aria-label="
              showPassword ? t('share.hidePassword') : t('share.showPassword')
            "
            @click="showPassword = !showPassword"
          >
            <svg
              v-if="showPassword"
              class="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
              />
            </svg>
            <svg
              v-else
              class="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
              />
            </svg>
          </button>
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">{{
          t('management.language')
        }}</label>
        <select
          v-model="form.language"
          class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500 bg-white"
        >
          <option value="zh-CN">简体中文</option>
          <option value="en-US">English</option>
          <option value="ja-JP">日本語</option>
          <option value="ko-KR">한국어</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">{{
          t('management.timezone')
        }}</label>
        <select
          v-model="form.timezone"
          class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500 bg-white"
        >
          <option value="Asia/Shanghai">Asia/Shanghai</option>
          <option value="UTC">UTC</option>
          <option value="America/New_York">America/New_York</option>
          <option value="Europe/London">Europe/London</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">{{
          t('management.selectGroups')
        }}</label>
        <div
          class="max-h-32 overflow-y-auto rounded-md border border-gray-300 bg-white p-2 space-y-2"
        >
          <label
            v-for="g in groups"
            :key="g.id"
            class="flex items-center gap-2 cursor-pointer hover:bg-gray-50 rounded px-2 py-1"
          >
            <input
              v-model="form.group_ids"
              type="checkbox"
              :value="g.id"
              class="h-4 w-4 shrink-0 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span class="text-sm text-gray-700">{{ g.name }}</span>
          </label>
          <p v-if="!groups.length" class="text-sm text-gray-500 py-1">
            {{ t('common.noData') }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3 py-1">
        <input
          id="user-form-is-staff"
          v-model="form.is_staff"
          type="checkbox"
          class="h-4 w-4 shrink-0 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <label
          for="user-form-is-staff"
          class="text-sm font-medium text-gray-700 cursor-pointer"
        >
          {{ t('management.setAsAdmin') }}
        </label>
      </div>

      <div v-if="isEdit" class="flex items-center gap-3 py-1">
        <input
          id="user-form-is-active"
          v-model="form.is_active"
          type="checkbox"
          class="h-4 w-4 shrink-0 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <label
          for="user-form-is-active"
          class="text-sm font-medium text-gray-700 cursor-pointer"
        >
          {{ t('management.accountEnabled') }}
        </label>
      </div>
    </form>
    <template #footer>
      <div class="flex flex-row-reverse gap-2">
        <BaseButton variant="primary" :loading="loading" @click="handleSubmit">
          {{ isEdit ? t('management.saveChanges') : t('common.confirm') }}
        </BaseButton>
        <BaseButton variant="outline" @click="handleClose">
          {{ t('common.cancel') }}
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  mode: {
    type: String,
    default: 'create',
    validator: (value) => ['create', 'edit'].includes(value)
  },
  user: {
    type: Object,
    default: null
  },
  groups: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close', 'submit'])

const { t } = useI18n()
const showPassword = ref(false)

const form = reactive(emptyForm())

const isEdit = computed(() => props.mode === 'edit')

const title = computed(() =>
  isEdit.value ? t('management.editUser') : t('management.createUser')
)

function emptyForm() {
  return {
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    is_staff: false,
    is_active: true,
    group_ids: [],
    language: 'zh-CN',
    timezone: 'Asia/Shanghai'
  }
}

function fillForm(user) {
  const source = user || {}
  Object.assign(form, emptyForm(), {
    username: source.username ?? '',
    email: source.email ?? '',
    first_name: source.first_name ?? '',
    last_name: source.last_name ?? '',
    is_staff: Boolean(source.is_staff),
    is_active: source.is_active !== false,
    group_ids: Array.isArray(source.groups)
      ? source.groups.map((group) => group.id)
      : [],
    language: source.language || 'zh-CN',
    timezone: source.timezone || 'Asia/Shanghai'
  })
  showPassword.value = false
}

watch(
  () => props.show,
  (isOpen) => {
    if (isOpen) fillForm(props.user)
  },
  { immediate: true }
)

function handleSubmit() {
  emit('submit', {
    username: (form.username || '').trim(),
    email: (form.email || '').trim(),
    first_name: (form.first_name || '').trim(),
    last_name: (form.last_name || '').trim(),
    password: (form.password || '').trim(),
    is_staff: form.is_staff,
    is_active: form.is_active,
    group_ids: Array.isArray(form.group_ids) ? form.group_ids : [],
    language: (form.language || '').trim() || 'zh-CN',
    timezone: (form.timezone || '').trim() || 'Asia/Shanghai'
  })
}

function handleClose() {
  emit('close')
}
</script>
