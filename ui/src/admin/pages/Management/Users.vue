<template>
  <AdminLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4">
        <h1 class="text-lg font-semibold text-gray-900">
          {{ t('management.userManagement') }}
        </h1>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('management.usersSubtitle') }}
        </p>
      </div>

      <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div class="p-6">
          <div class="flex flex-wrap items-center justify-between gap-3 mb-6">
            <span class="text-sm text-gray-600">{{
              t('management.totalUsers', { count: totalCount })
            }}</span>
            <div class="flex items-center gap-2">
              <BaseButton
                variant="outline"
                size="sm"
                :loading="loading"
                @click="fetchUsers"
              >
                {{ t('common.refresh') }}
              </BaseButton>
              <BaseButton variant="primary" size="sm" @click="openCreateModal">
                {{ t('management.createUser') }}
              </BaseButton>
            </div>
          </div>

          <BaseLoading v-if="loading && !users.length" />

          <div
            v-else-if="error"
            class="py-16 text-center rounded-lg border border-gray-200 bg-gray-50"
          >
            <p class="text-sm font-medium text-red-600">{{ error }}</p>
          </div>

          <div
            v-else-if="!users.length"
            class="py-16 text-center rounded-lg border border-gray-200 bg-gray-50"
          >
            <p class="text-sm font-medium text-gray-600">
              {{ t('common.noData') }}
            </p>
          </div>

          <div
            v-else
            class="overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
          >
            <table class="min-w-full divide-y divide-gray-200">
              <colgroup>
                <col class="w-16" />
                <col class="w-40" />
                <col class="w-40" />
                <col class="w-56" />
                <col class="w-20" />
                <col class="w-20" />
                <col class="w-28" />
                <col class="w-36" />
                <col class="w-48" />
                <col class="w-48" />
                <col class="w-24" />
              </colgroup>
              <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.id') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.username') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.displayName') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.email') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.isStaff') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.isActive') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.language') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.timezone') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.groups') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.dateJoined') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('management.actions') }}
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-100">
                <tr
                  v-for="u in users"
                  :key="u.id"
                  class="hover:bg-gray-50 transition-colors duration-150"
                >
                  <td class="px-4 py-4 text-sm text-gray-900">{{ u.id }}</td>
                  <td class="px-4 py-4 text-sm font-medium text-gray-900">
                    {{ u.username }}
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    {{ u.display_name || '—' }}
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    {{ u.email || '—' }}
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    <span
                      class="inline-flex items-center justify-center rounded-full p-1.5"
                      :class="
                        u.is_staff
                          ? 'bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-200'
                          : 'bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-200'
                      "
                      :title="
                        u.is_staff
                          ? t('management.staffStatusAdmin')
                          : t('management.staffStatusUser')
                      "
                      :aria-label="
                        u.is_staff
                          ? t('management.staffStatusAdmin')
                          : t('management.staffStatusUser')
                      "
                    >
                      <svg
                        v-if="u.is_staff"
                        class="h-4 w-4"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path
                          d="M12 3l7 4v5c0 5-3.5 8.5-7 9-3.5-.5-7-4-7-9V7l7-4z"
                        />
                        <path d="M9 12l2 2 4-4" />
                      </svg>
                      <svg
                        v-else
                        class="h-4 w-4"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M12 12a4 4 0 100-8 4 4 0 000 8z" />
                        <path d="M4 20a8 8 0 0116 0" />
                      </svg>
                    </span>
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    <span
                      class="inline-flex items-center justify-center rounded-full p-1.5"
                      :class="
                        u.is_active !== false
                          ? 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200'
                          : 'bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-200'
                      "
                      :title="
                        u.is_active !== false
                          ? t('management.activeStatusEnabled')
                          : t('management.activeStatusDisabled')
                      "
                      :aria-label="
                        u.is_active !== false
                          ? t('management.activeStatusEnabled')
                          : t('management.activeStatusDisabled')
                      "
                    >
                      <svg
                        v-if="u.is_active !== false"
                        class="h-4 w-4"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M12 2a10 10 0 100 20 10 10 0 000-20z" />
                        <path d="M8 12l2.5 2.5L16 9" />
                      </svg>
                      <svg
                        v-else
                        class="h-4 w-4"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M12 2a10 10 0 100 20 10 10 0 000-20z" />
                        <path d="M9 9l6 6M15 9l-6 6" />
                      </svg>
                    </span>
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    <span
                      class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap"
                      :class="
                        u.language
                          ? 'bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-200'
                          : 'bg-gray-100 text-gray-500 ring-1 ring-inset ring-gray-200'
                      "
                    >
                      {{ u.language || '—' }}
                    </span>
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    <span
                      class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-mono whitespace-nowrap"
                      :class="
                        u.timezone
                          ? 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200'
                          : 'bg-gray-100 text-gray-500 ring-1 ring-inset ring-gray-200'
                      "
                    >
                      {{ u.timezone || '—' }}
                    </span>
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    {{
                      u.groups && u.groups.length
                        ? u.groups.map((g) => g.name).join(', ')
                        : '—'
                    }}
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    <span class="whitespace-nowrap text-sm text-gray-500">
                      {{ formatDate(u.date_joined) }}
                    </span>
                  </td>
                  <td class="px-4 py-4 text-sm text-gray-500">
                    <BaseButton
                      variant="outline"
                      size="sm"
                      @click="openEditModal(u)"
                    >
                      {{ t('management.edit') }}
                    </BaseButton>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div
            v-if="!loading && totalCount > 0"
            class="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 pt-4"
          >
            <p class="text-sm text-gray-600">
              {{ t('common.pagination.showing', paginationShowing) }}
            </p>
            <div class="flex items-center gap-2">
              <label class="text-sm text-gray-600"
                >{{ t('common.pagination.itemsPerPage') }}:</label
              >
              <select
                v-model.number="pageSize"
                class="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                @change="handlePageSizeChange"
              >
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
              </select>
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage <= 1"
                @click="goToPreviousPage"
              >
                {{ t('common.pagination.previous') }}
              </BaseButton>
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage >= totalPages"
                @click="goToNextPage"
              >
                {{ t('common.pagination.next') }}
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <UserFormModal
        :show="showFormModal"
        :mode="formMode"
        :user="editingUser"
        :groups="groupOptions"
        :loading="formLoading"
        :error="formError"
        @close="closeFormModal"
        @submit="submitUserForm"
      />
    </div>
  </AdminLayout>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import UserFormModal from '@/admin/pages/Management/UserFormModal.vue'
import { managementApi } from '@/admin/api'

const { t } = useI18n()
const users = ref([])
const loading = ref(false)
const error = ref(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)
const showFormModal = ref(false)
const formMode = ref('create')
const editingUser = ref(null)
const formLoading = ref(false)
const formError = ref(null)
const groupOptions = ref([])

const totalPages = computed(() =>
  totalCount.value > 0 ? Math.ceil(totalCount.value / pageSize.value) : 1
)

const paginationShowing = computed(() => ({
  from:
    totalCount.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1,
  to: Math.min(currentPage.value * pageSize.value, totalCount.value),
  total: totalCount.value
}))

function closeFormModal() {
  showFormModal.value = false
  editingUser.value = null
  formError.value = null
}

async function openCreateModal() {
  formMode.value = 'create'
  editingUser.value = null
  formError.value = null
  showFormModal.value = true
  await loadGroupOptions()
}

async function openEditModal(user) {
  formMode.value = 'edit'
  editingUser.value = user
  formError.value = null
  showFormModal.value = true
  if (!groupOptions.value.length) await loadGroupOptions()
}

async function loadGroupOptions() {
  try {
    const data = await managementApi.getGroups({ page: 1, page_size: 1000 })
    groupOptions.value = Array.isArray(data) ? data : (data?.results ?? [])
  } catch {
    groupOptions.value = []
  }
}

function formErrorFromResponse(e) {
  const body = e?.response?.data
  const codeMessages = {
    username_required: t('management.usernameRequired'),
    password_required: t('management.passwordRequired'),
    username_taken: t('management.usernameTaken'),
    username_immutable: t('management.usernameImmutable'),
    email_taken: t('management.emailTaken'),
    cannot_revoke_own_admin: t('management.cannotRevokeOwnAdmin'),
    cannot_deactivate_self: t('management.cannotDeactivateSelf'),
    superuser_protected: t('management.superuserProtected')
  }
  if (body?.code && codeMessages[body.code]) return codeMessages[body.code]
  if (typeof body?.detail === 'string') return body.detail
  return e?.message || t('common.error')
}

async function submitUserForm(payload) {
  formError.value = null
  if (formMode.value === 'create') {
    if (!payload.username) {
      formError.value = t('management.usernameRequired')
      return
    }
    if (!payload.password) {
      formError.value = t('management.passwordRequired')
      return
    }
  }
  formLoading.value = true
  try {
    if (formMode.value === 'create') {
      await managementApi.createUser(payload)
    } else {
      const body = { ...payload }
      delete body.username
      if (!body.password) delete body.password
      await managementApi.updateUser(editingUser.value.id, body)
    }
    closeFormModal()
    await fetchUsers()
  } catch (e) {
    formError.value = formErrorFromResponse(e)
  } finally {
    formLoading.value = false
  }
}

function formatDate(value) {
  if (!value) return '—'
  try {
    const d = new Date(value)
    return Number.isNaN(d.getTime()) ? value : d.toLocaleString()
  } catch {
    return value
  }
}

async function handlePageSizeChange() {
  currentPage.value = 1
  await fetchUsers()
}

async function goToPreviousPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  await fetchUsers()
}

async function goToNextPage() {
  if (currentPage.value >= totalPages.value) return
  currentPage.value += 1
  await fetchUsers()
}

async function fetchUsers() {
  loading.value = true
  error.value = null
  try {
    const data = await managementApi.getUsers({
      page: currentPage.value,
      page_size: pageSize.value
    })
    if (Array.isArray(data)) {
      users.value = data
      totalCount.value = data.length
    } else {
      users.value = data?.results ?? []
      totalCount.value = Number(data?.count ?? users.value.length)
    }
  } catch (e) {
    users.value = []
    totalCount.value = 0
    error.value = e?.response?.data?.detail || e?.message || t('common.error')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchUsers()
})
</script>
