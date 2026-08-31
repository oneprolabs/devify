<template>
  <div class="space-y-4">
    <!-- The virtual address is always live; it is a channel that runs
         alongside any mailbox, not an alternative to one. -->
    <div class="rounded-lg border border-blue-200 bg-blue-50 p-3">
      <div class="text-xs font-medium text-blue-700">
        {{ t('settings.currentAutoAssignedEmail') }}
      </div>
      <div
        class="mt-1 truncate font-mono text-sm text-blue-900"
        :title="virtualEmail || t('settings.noVirtualEmail')"
      >
        {{ virtualEmail || t('settings.noVirtualEmail') }}
      </div>
      <p class="mt-2 text-xs text-blue-700">
        {{ t('settings.virtualAlwaysOn') }}
      </p>
    </div>

    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h4 class="text-sm font-medium text-gray-900">
            {{ t('settings.mailboxesTitle') }}
          </h4>
          <p class="mt-0.5 text-xs text-gray-500">
            {{ t('settings.mailboxesDesc', { max: maxMailboxes }) }}
          </p>
        </div>
        <BaseButton
          v-if="!showForm && mailboxes.length < maxMailboxes"
          type="button"
          size="sm"
          variant="secondary"
          @click="startAdd"
        >
          {{ t('settings.addMailbox') }}
        </BaseButton>
      </div>

      <p v-if="error" class="rounded-md bg-red-50 p-3 text-sm text-red-700">
        {{ error }}
      </p>

      <p
        v-else-if="notice"
        class="rounded-md bg-green-50 p-3 text-sm font-medium text-green-800"
      >
        {{ notice }}
      </p>

      <p
        v-if="!mailboxes.length && !showForm"
        class="rounded-lg border border-dashed border-gray-300 py-6 text-center text-sm text-gray-500"
      >
        {{ t('settings.noMailboxes') }}
      </p>

      <ul v-else-if="mailboxes.length" class="space-y-2">
        <li
          v-for="box in mailboxes"
          :key="box.uuid"
          class="rounded-lg border border-gray-200 p-3"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-gray-900">
                {{ box.display_name }}
              </p>
              <p class="mt-0.5 truncate text-xs text-gray-500">
                {{ box.imap_host }}:{{ box.imap_port }} · {{ box.folder }}
              </p>
              <p class="mt-1 text-xs" :class="statusClass(box)">
                {{ statusText(box) }}
              </p>
            </div>

            <div class="flex flex-shrink-0 gap-2">
              <BaseButton
                type="button"
                size="sm"
                variant="secondary"
                :loading="testing === box.uuid"
                @click="testStored(box)"
              >
                {{ t('settings.validateConnection') }}
              </BaseButton>
              <BaseButton
                type="button"
                size="sm"
                variant="secondary"
                @click="startEdit(box)"
              >
                {{ t('common.edit') }}
              </BaseButton>
              <BaseButton
                type="button"
                size="sm"
                variant="danger"
                :loading="removing === box.uuid"
                @click="remove(box)"
              >
                {{ t('common.delete') }}
              </BaseButton>
            </div>
          </div>
        </li>
      </ul>

      <div
        v-if="showForm"
        class="space-y-4 rounded-lg border border-gray-200 bg-gray-50 p-4"
      >
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BaseInput
            v-model="form.imap_host"
            :label="t('settings.imapHost')"
            :placeholder="t('settings.imapHostPlaceholder')"
          />
          <BaseInput
            v-model="form.username"
            :label="t('settings.imapUsername')"
            :placeholder="t('settings.imapUsernamePlaceholder')"
          />
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BaseInput
            v-model="form.password"
            :label="t('settings.imapPassword')"
            type="password"
            name="mailbox_password"
            autocomplete="new-password"
            :placeholder="
              editing
                ? t('settings.passwordUnchanged')
                : t('settings.imapPasswordPlaceholder')
            "
          />
          <BaseInput
            v-model="form.imap_port"
            :label="t('settings.imapSslPort')"
            type="number"
            :placeholder="t('settings.imapSslPortPlaceholder')"
          />
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BaseInput
            v-model="form.name"
            :label="t('settings.mailboxName')"
            :placeholder="t('settings.mailboxNamePlaceholder')"
          />
          <BaseInput
            v-model="form.folder"
            :label="t('settings.imapFolder')"
            :placeholder="t('settings.imapFolderPlaceholder')"
          />
        </div>

        <div class="flex flex-wrap gap-4">
          <label class="flex items-center gap-2 text-sm text-gray-700">
            <input
              v-model="form.use_ssl"
              type="checkbox"
              class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            {{ t('settings.useSsl') }}
          </label>
          <label class="flex items-center gap-2 text-sm text-gray-700">
            <input
              v-model="form.delete_after_fetch"
              type="checkbox"
              class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            {{ t('settings.deleteAfterFetch') }}
          </label>
          <label class="flex items-center gap-2 text-sm text-gray-700">
            <input
              v-model="form.enabled"
              type="checkbox"
              class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            {{ t('settings.mailboxEnabled') }}
          </label>
        </div>

        <div class="flex flex-wrap justify-end gap-2">
          <BaseButton type="button" variant="secondary" @click="cancel">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton
            type="button"
            variant="secondary"
            :loading="testing === 'draft'"
            @click="testDraft"
          >
            {{ t('settings.validateConnection') }}
          </BaseButton>
          <BaseButton type="button" :loading="saving" @click="save">
            {{ t('common.save') }}
          </BaseButton>
        </div>
      </div>
    </div>
  </div>

  <ConfirmDialog
    :show="!!pendingRemoval"
    :title="t('settings.confirmRemoveMailboxTitle')"
    :message="t('settings.confirmRemoveMailbox')"
    :confirm-text="t('common.delete')"
    variant="danger"
    :loading="!!removing"
    @close="pendingRemoval = null"
    @confirm="confirmRemoval"
  />
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { mailboxApi } from '@/api/mailboxes'

defineProps({
  virtualEmail: {
    type: String,
    default: ''
  }
})

const { t, locale } = useI18n()

const mailboxes = ref([])
const maxMailboxes = ref(5)
const showForm = ref(false)
const editing = ref(null)
const saving = ref(false)
const testing = ref('')
const removing = ref('')
const error = ref('')
const notice = ref('')
const pendingRemoval = ref(null)

const emptyForm = () => ({
  name: '',
  imap_host: '',
  imap_port: 993,
  username: '',
  password: '',
  folder: 'INBOX',
  use_ssl: true,
  delete_after_fetch: false,
  enabled: true
})

const form = reactive(emptyForm())

let noticeTimer = null

function clearFeedback() {
  error.value = ''
  notice.value = ''
}

function showNotice(message) {
  notice.value = message
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => {
    notice.value = ''
  }, 4000)
}

function readError(err, fallbackKey) {
  const data = err?.response?.data
  if (data?.message) return data.message
  if (data && typeof data === 'object') {
    const first = Object.values(data)[0]
    if (Array.isArray(first)) return first[0]
    if (typeof first === 'string') return first
  }
  return t(fallbackKey)
}

async function load() {
  error.value = ''
  try {
    const data = await mailboxApi.list()
    mailboxes.value = data.mailboxes || []
    maxMailboxes.value = data.max_mailboxes ?? 5
  } catch (err) {
    error.value = readError(err, 'settings.mailboxLoadFailed')
  }
}

function statusText(box) {
  if (!box.enabled) return t('settings.mailboxDisabled')
  if (box.last_error) {
    return t('settings.mailboxFailing', {
      count: box.consecutive_failures,
      error: box.last_error
    })
  }
  if (box.last_success_at) {
    return t('settings.mailboxLastSuccess', {
      time: new Date(box.last_success_at).toLocaleString(locale.value)
    })
  }
  return t('settings.mailboxNeverFetched')
}

function statusClass(box) {
  if (!box.enabled) return 'text-gray-400'
  return box.last_error ? 'text-red-600' : 'text-gray-500'
}

function startAdd() {
  Object.assign(form, emptyForm())
  editing.value = null
  showForm.value = true
}

function startEdit(box) {
  Object.assign(form, {
    name: box.name,
    imap_host: box.imap_host,
    imap_port: box.imap_port,
    username: box.username,
    // Left blank on purpose: an empty value keeps the stored password.
    password: '',
    folder: box.folder,
    use_ssl: box.use_ssl,
    delete_after_fetch: box.delete_after_fetch,
    enabled: box.enabled
  })
  editing.value = box
  showForm.value = true
}

function cancel() {
  showForm.value = false
  editing.value = null
  error.value = ''
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const payload = { ...form }
    if (editing.value && !payload.password) delete payload.password
    if (editing.value) {
      await mailboxApi.update(editing.value.uuid, payload)
    } else {
      await mailboxApi.create(payload)
    }
    cancel()
    await load()
  } catch (err) {
    error.value = readError(err, 'settings.mailboxSaveFailed')
  } finally {
    saving.value = false
  }
}

async function testDraft() {
  testing.value = 'draft'
  clearFeedback()
  try {
    // When editing, the password field is left blank to keep the stored
    // one; send the uuid so the test can use it too.
    const payload = { ...form }
    if (editing.value) payload.uuid = editing.value.uuid
    await mailboxApi.testDraft(payload)
    showNotice(t('settings.connectionOk'))
  } catch (err) {
    error.value = readError(err, 'settings.connectionFailed')
  } finally {
    testing.value = ''
  }
}

async function testStored(box) {
  testing.value = box.uuid
  clearFeedback()
  try {
    await mailboxApi.testStored(box.uuid)
    showNotice(t('settings.connectionOkFor', { name: box.display_name }))
  } catch (err) {
    error.value = readError(err, 'settings.connectionFailed')
  } finally {
    testing.value = ''
    await load()
  }
}

function remove(box) {
  pendingRemoval.value = box
}

async function confirmRemoval() {
  const box = pendingRemoval.value
  if (!box) return
  removing.value = box.uuid
  clearFeedback()
  try {
    await mailboxApi.remove(box.uuid)
    pendingRemoval.value = null
    await load()
  } catch (err) {
    error.value = readError(err, 'settings.mailboxSaveFailed')
  } finally {
    removing.value = ''
  }
}

onMounted(load)
</script>
