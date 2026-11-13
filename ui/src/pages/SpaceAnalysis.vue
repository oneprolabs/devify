<template>
  <AppLayout :padded="false">
    <div class="analysis-page">
      <div v-if="error" class="ws-alert" role="alert">{{ error }}</div>

      <div class="analysis-body">
        <div class="analysis-main">
          <AskWorkspace
            v-if="route.query.panel === 'ask'"
            :space-id="spaceId"
            :initial-question="String(route.query.q || '')"
            @select-citation="openEvidence"
          />
          <EventWorkspace
            v-else-if="activeTab === 'events'"
            :space-id="spaceId"
            :events="items.events"
            :selected="selected"
            :loading="loading"
            :detail-loading="detailLoading"
            :has-more="eventsHaveMore"
            :loading-more="eventsLoadingMore"
            :can-edit="canManage"
            :can-create="canCreate"
            @select="selectItem"
            @refresh="loadActive"
            @show-notes="openNotes"
            @edit="openEditForm"
            @create="openCreateForm"
            @ask="askAboutEvent"
            @load-more="loadMoreEvents"
            @select-citation="openEvidence"
          />
          <NoteWorkspace
            v-else-if="activeTab === 'notes'"
            :space-id="spaceId"
            :notes="items.notes"
            :selected="selected"
            :loading="loading"
            :detail-loading="detailLoading"
            :can-create="canCreate"
            :can-edit="canManage"
            @select="selectItem"
            @create="openCreateForm"
            @edit="openEditForm"
            @add-evidence="addEvidence"
            @open-event="openEventEvidence"
            @open-message="openEvidence"
            @back-events="backToEvents"
          />
          <ReportWorkspace
            v-else
            :space-id="spaceId"
            :reports="items.reports"
            :selected="selected"
            :loading="loading"
            :detail-loading="detailLoading"
            :can-create="canCreate"
            @select="selectItem"
            @refresh="loadActive"
            @create="openCreateForm"
            @open-citation="openEvidence"
          />
        </div>
        <EvidenceDrawer
          v-if="evidence"
          :space-id="spaceId"
          :target="evidence"
          @close="closeEvidence"
          @navigate="openEvidence"
          @open-detail="openEvidenceDetail"
        />
      </div>

      <div v-if="formOpen" class="ws-modal-backdrop" @click.self="closeForm">
        <form class="ws-modal" @submit.prevent="submitForm">
          <div class="ws-modal-head">
            <h2>{{ formTitle }}</h2>
            <button type="button" class="ws-btn ghost" @click="closeForm">
              {{ t('common.close') }}
            </button>
          </div>
          <label class="ws-field">
            <span>{{ t('spaces.titleField') }}</span>
            <input v-model="form.title" required maxlength="500" />
          </label>
          <label v-if="form.kind !== 'report'" class="ws-field">
            <span>{{ t('spaces.contentField') }}</span>
            <textarea v-model="form.content" required rows="5"></textarea>
          </label>
          <div class="ws-modal-actions">
            <button type="button" class="ws-btn" @click="closeForm">
              {{ t('common.cancel') }}
            </button>
            <button
              type="submit"
              class="ws-btn primary"
              :disabled="formSubmitting"
            >
              {{ formSubmitting ? t('common.saving') : t('common.save') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import AskWorkspace from '@/components/spaces/AskWorkspace.vue'
import EvidenceDrawer from '@/components/spaces/EvidenceDrawer.vue'
import EventWorkspace from '@/components/spaces/EventWorkspace.vue'
import NoteWorkspace from '@/components/spaces/NoteWorkspace.vue'
import ReportWorkspace from '@/components/spaces/ReportWorkspace.vue'
import { spacesApi } from '@/api/spaces'

const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})
const { t } = useI18n()
const router = useRouter()
const route = useRoute()

const space = ref(null)
const activeTab = ref('events')
const items = ref({ notes: [], events: [], reports: [] })
const selected = ref(null)
const eventsHaveMore = ref(false)
const eventsLoadingMore = ref(false)
const loading = ref(false)
const detailLoading = ref(false)
const error = ref('')
const formOpen = ref(false)
const formSubmitting = ref(false)
const formMode = ref('create')
const form = reactive({ kind: 'note', title: '', key: '', content: '' })

const canCreate = computed(
  () =>
    !!space.value &&
    space.value.status === 'active' &&
    (space.value.is_global_admin
      ? space.value.admin_takeover_active
      : ['owner', 'maintainer', 'user'].includes(space.value.role))
)
const canManage = computed(
  () =>
    !!space.value &&
    space.value.status === 'active' &&
    (space.value.is_global_admin
      ? space.value.admin_takeover_active
      : ['owner', 'maintainer'].includes(space.value.role))
)
const listData = (response) => (response.data.data || response.data).list || []

function tabFromRoute() {
  if (route.query.tab === 'reports' || route.query.report) return 'reports'
  if (route.query.tab === 'notes' || route.query.note) return 'notes'
  return 'events'
}

const loadSpace = async () => {
  const response = await spacesApi.getSpaces()
  const data = response.data.data || response.data
  space.value =
    (Array.isArray(data) ? data : data.list || []).find(
      (item) => String(item.id) === String(props.spaceId)
    ) || null
}

let listRequestId = 0
let detailRequestId = 0
const loadActive = async () => {
  const requestId = ++listRequestId
  ++detailRequestId
  const tab = activeTab.value
  const spaceId = props.spaceId
  selected.value = null
  detailLoading.value = false
  loading.value = true
  error.value = ''
  try {
    const response =
      tab === 'notes'
        ? await spacesApi.getNotes(spaceId, { page_size: 100 })
        : tab === 'events'
          ? await spacesApi.getEvents(spaceId, { page_size: 100 })
          : await spacesApi.getReports(spaceId, { page_size: 100 })
    if (requestId !== listRequestId) return
    items.value[tab] = listData(response)
    if (tab === 'events')
      eventsHaveMore.value = !!(response.data.data || response.data).pagination
        ?.next
    const requestedId =
      tab === 'events'
        ? route.query.event
        : tab === 'notes'
          ? route.query.note
          : route.query.report
    const requested = requestedId
      ? items.value[tab].find((item) => String(item.id) === String(requestedId))
      : null
    if (requested) selectItem(requested)
    else if (items.value[tab].length) selectItem(items.value[tab][0])
  } catch (requestError) {
    if (requestId === listRequestId)
      error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    if (requestId === listRequestId) loading.value = false
  }
}

const loadMoreEvents = async () => {
  if (!eventsHaveMore.value || eventsLoadingMore.value) return
  eventsLoadingMore.value = true
  try {
    const response = await spacesApi.getEvents(props.spaceId, {
      page: Math.floor(items.value.events.length / 100) + 1,
      page_size: 100
    })
    const data = response.data.data || response.data
    items.value.events = [...items.value.events, ...(data.list || [])]
    eventsHaveMore.value = Boolean(data.pagination?.next)
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    eventsLoadingMore.value = false
  }
}

const selectItem = async (item) => {
  const requestId = ++detailRequestId
  const tab = activeTab.value
  selected.value = item
  detailLoading.value = true
  try {
    const response =
      tab === 'notes'
        ? await spacesApi.getNote(item.id)
        : tab === 'events'
          ? await spacesApi.getEvent(item.id)
          : await spacesApi.getReport(item.id)
    if (requestId === detailRequestId)
      selected.value = response.data.data || response.data
  } catch (requestError) {
    if (requestId === detailRequestId)
      error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    if (requestId === detailRequestId) detailLoading.value = false
  }
}

const evidence = ref(null)
let evidenceTrigger = null
const openEvidence = (citation) => {
  if (!citation) return
  evidenceTrigger = document.activeElement
  evidence.value = { ...citation }
}
const closeEvidence = async () => {
  evidence.value = null
  await nextTick()
  evidenceTrigger?.focus?.()
  evidenceTrigger = null
}
const openEventEvidence = (eventId) => {
  openEvidence({ kind: 'event', id: eventId })
}
const openEvidenceDetail = async (citation) => {
  await closeEvidence()
  if (!citation) return
  if (citation.kind === 'event') {
    await router.push({
      path: `/spaces/${props.spaceId}/analysis`,
      query: { event: citation.id }
    })
  } else if (citation.kind === 'note') {
    await router.push({
      path: `/spaces/${props.spaceId}/analysis`,
      query: { note: citation.id }
    })
  } else {
    await router.push(
      `/spaces/${props.spaceId}/chats?conversation_id=${citation.conversation_id || ''}&message_id=${citation.id}`
    )
  }
}
const openNotes = () => {
  activeTab.value = 'notes'
  loadActive()
}
const backToEvents = () => {
  activeTab.value = 'events'
  if (route.query.note || route.query.tab === 'notes')
    router.replace({ path: route.path, query: {} })
  loadActive()
}
const askAboutEvent = async (question) => {
  await router.push({
    path: `/spaces/${props.spaceId}/analysis`,
    query: { panel: 'ask', q: question }
  })
}

const formTitle = computed(() =>
  formMode.value === 'edit'
    ? t('spaces.editItem')
    : form.kind === 'note'
      ? t('spaces.newNote')
      : form.kind === 'event'
        ? t('spaces.newEvent')
        : t('spaces.newReport')
)
const openCreateForm = () => {
  formMode.value = 'create'
  form.kind =
    activeTab.value === 'reports'
      ? 'report'
      : activeTab.value === 'events'
        ? 'event'
        : 'note'
  form.title = ''
  form.key = `${form.kind}-${Date.now()}`
  form.content = ''
  formOpen.value = true
}
const openEditForm = () => {
  if (
    !selected.value ||
    (activeTab.value !== 'notes' && activeTab.value !== 'events')
  )
    return
  formMode.value = 'edit'
  form.kind = activeTab.value === 'events' ? 'event' : 'note'
  form.title = selected.value.title
  form.key = selected.value.note_key || selected.value.event_key || ''
  form.content = selected.value.content || ''
  formOpen.value = true
}
const closeForm = () => {
  formOpen.value = false
}
const submitForm = async () => {
  formSubmitting.value = true
  try {
    let response
    if (formMode.value === 'edit') {
      response =
        form.kind === 'note'
          ? await spacesApi.updateNote(selected.value.id, {
              title: form.title,
              content: form.content
            })
          : await spacesApi.updateEvent(selected.value.id, {
              title: form.title,
              content: form.content
            })
    } else if (form.kind === 'note') {
      response = await spacesApi.createNote(props.spaceId, {
        note_key: form.key,
        title: form.title,
        content: form.content,
        origin: 'manual'
      })
    } else if (form.kind === 'event') {
      response = await spacesApi.createEvent(props.spaceId, {
        event_key: form.key,
        title: form.title,
        content: form.content,
        status: 'open'
      })
    } else {
      response = await spacesApi.createReport(props.spaceId, {
        request_key: form.key,
        title: form.title
      })
    }
    formOpen.value = false
    await loadActive()
    if (response?.data?.data) await selectItem(response.data.data)
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    formSubmitting.value = false
  }
}
const addEvidence = async (messageId) => {
  if (!selected.value || !messageId) return
  try {
    await spacesApi.addNoteEvidence(selected.value.id, {
      message_id: messageId
    })
    await selectItem(selected.value)
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  }
}

watch(
  () => [
    route.query.tab,
    route.query.panel,
    route.query.event,
    route.query.note,
    route.query.report
  ],
  () => {
    if (route.query.panel === 'ask') return
    activeTab.value = tabFromRoute()
    loadActive()
  }
)
watch(
  () => props.spaceId,
  async () => {
    await loadSpace()
    await loadActive()
  }
)
onMounted(async () => {
  activeTab.value = tabFromRoute()
  try {
    await loadSpace()
    await loadActive()
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  }
})
</script>

<style scoped>
.analysis-page {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  background: rgb(var(--c-bg));
  color: rgb(var(--c-tx));
}
.analysis-body {
  display: flex;
  min-height: 0;
  flex: 1;
}
.analysis-main {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}
</style>
