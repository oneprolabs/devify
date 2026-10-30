<template>
  <AppLayout :padded="false">
    <div class="analysis-page">
      <header class="analysis-header">
        <div class="analysis-heading">
          <router-link :to="`/spaces/${spaceId}/chats`" class="analysis-back">{{
            t('common.back')
          }}</router-link>
          <div>
            <h1>{{ space?.name || t('spaces.title') }}</h1>
            <p>{{ t('spaces.analysisWorkspace') }}</p>
          </div>
        </div>
        <router-link to="/spaces" class="analysis-switch">{{
          t('spaces.switchSpace')
        }}</router-link>
      </header>
      <div v-if="error" class="analysis-alert" role="alert">{{ error }}</div>
      <nav class="analysis-tabs" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.value"
          class="analysis-tab"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }} <span>{{ items[tab.value].length }}</span>
        </button>
        <div class="analysis-actions">
          <button type="button" class="analysis-action" @click="openCreateForm">
            {{
              activeTab === 'notes'
                ? t('spaces.newNote')
                : activeTab === 'events'
                  ? t('spaces.newEvent')
                  : t('spaces.newReport')
            }}
          </button>
        </div>
      </nav>
      <form v-if="formOpen" class="analysis-form" @submit.prevent="submitForm">
        <div class="analysis-form-head">
          <h2>{{ formTitle }}</h2>
          <button type="button" class="form-close" @click="closeForm">
            {{ t('common.close') }}
          </button>
        </div>
        <div class="form-grid">
          <label
            ><span>{{ t('spaces.titleField') }}</span
            ><input v-model="form.title" required maxlength="500"
          /></label>
          <label
            ><span>{{ t('spaces.keyField') }}</span
            ><input v-model="form.key" required maxlength="255"
          /></label>
          <label class="form-wide"
            ><span>{{ t('spaces.contentField') }}</span
            ><textarea v-model="form.content" required rows="4"></textarea>
          </label>
        </div>
        <div class="form-actions">
          <button
            type="submit"
            class="analysis-action primary"
            :disabled="formSubmitting"
          >
            {{ formSubmitting ? t('common.saving') : t('common.save') }}
          </button>
        </div>
      </form>
      <main class="analysis-body">
        <section class="analysis-list">
          <div class="analysis-list-head">
            <div>
              <h2>{{ activeLabel }}</h2>
              <p>{{ activeDescription }}</p>
            </div>
            <button
              type="button"
              class="analysis-refresh"
              :disabled="loading"
              @click="loadActive"
            >
              {{ t('common.refresh') }}
            </button>
          </div>
          <div v-if="loading" class="analysis-state" aria-busy="true">
            {{ t('common.loading') }}
          </div>
          <div
            v-else-if="!activeItems.length"
            class="analysis-state"
            role="status"
          >
            <strong>{{ emptyTitle }}</strong
            ><span>{{ emptyBody }}</span>
          </div>
          <div v-else class="analysis-items" role="list">
            <button
              v-for="item in activeItems"
              :key="item.id"
              type="button"
              class="analysis-item"
              :class="{ active: selected?.id === item.id }"
              role="listitem"
              @click="selectItem(item)"
            >
              <span class="analysis-item-main"
                ><strong>{{ item.title }}</strong
                ><span>{{ summaryFor(item) }}</span></span
              >
              <span class="analysis-item-meta">{{ metaFor(item) }}</span>
            </button>
          </div>
        </section>
        <aside class="analysis-detail" aria-live="polite">
          <div v-if="detailLoading" class="analysis-state" aria-busy="true">
            {{ t('common.loading') }}
          </div>
          <div
            v-else-if="!selected"
            class="analysis-state detail-placeholder"
            role="status"
          >
            <strong>{{ t('spaces.selectAnalysisItem') }}</strong
            ><span>{{ t('spaces.selectAnalysisItemBody') }}</span>
          </div>
          <template v-else-if="activeTab === 'notes'">
            <div class="detail-head">
              <span class="detail-kicker">{{ t('spaces.note') }}</span>
              <h2>{{ selected.title }}</h2>
              <p>{{ selected.origin }} · {{ selected.assignment_mode }}</p>
            </div>
            <div class="detail-content">{{ selected.content }}</div>
            <div class="detail-toolbar">
              <button type="button" class="text-action" @click="openEditForm">
                {{ t('common.edit') }}
              </button>
            </div>
            <div class="detail-section">
              <h3>{{ t('spaces.evidence') }}</h3>
              <div v-if="!selected.evidence?.length" class="detail-muted">
                {{ t('spaces.noEvidence') }}
              </div>
              <div
                v-for="evidence in selected.evidence || []"
                :key="evidence.id"
                class="evidence-row"
              >
                <span>#{{ evidence.message_id }}</span
                ><small>{{ evidence.reference_key }}</small>
              </div>
            </div>
            <div class="detail-section">
              <h3>{{ t('spaces.events') }}</h3>
              <span
                v-for="eventId in selected.event_ids || []"
                :key="eventId"
                class="id-chip"
                >Event #{{ eventId }}</span
              >
              <div v-if="!selected.event_ids?.length" class="detail-muted">
                {{ t('spaces.noEventLinks') }}
              </div>
              <div class="inline-action">
                <input
                  v-model="evidenceMessageId"
                  inputmode="numeric"
                  :placeholder="t('spaces.messageId')"
                /><select v-model="relationKind" class="relation-select">
                  <option value="related">
                    {{ t('spaces.relationRelated') }}
                  </option>
                  <option value="same">{{ t('spaces.relationSame') }}</option>
                  <option value="separate">
                    {{ t('spaces.relationSeparate') }}
                  </option>
                  <option value="depends_on">
                    {{ t('spaces.relationDepends') }}
                  </option></select
                ><select v-model="relationDecision" class="relation-select">
                  <option value="pending">
                    {{ t('spaces.relationPending') }}
                  </option>
                  <option value="accepted">
                    {{ t('spaces.relationAccepted') }}
                  </option>
                  <option value="rejected">
                    {{ t('spaces.relationRejected') }}
                  </option></select
                ><button type="button" class="text-action" @click="addEvidence">
                  {{ t('spaces.addEvidence') }}
                </button>
              </div>
              <div class="suggestion-list">
                <h3>{{ t('spaces.suggestions') }}</h3>
                <div v-if="!suggestions.length" class="detail-muted">
                  {{ t('spaces.noSuggestions') }}
                </div>
                <div
                  v-for="suggestion in suggestions"
                  :key="suggestion.id"
                  class="suggestion-row"
                >
                  <div>
                    <strong>{{ suggestion.title }}</strong>
                    <p>{{ suggestion.summary }}</p>
                  </div>
                  <div>
                    <button
                      type="button"
                      class="text-action"
                      @click="reviewSuggestion(suggestion, 'accepted')"
                    >
                      {{ t('spaces.accept') }}</button
                    ><button
                      type="button"
                      class="text-danger"
                      @click="reviewSuggestion(suggestion, 'rejected')"
                    >
                      {{ t('spaces.reject') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <template v-else-if="activeTab === 'events'">
            <div class="detail-head">
              <span class="detail-kicker">{{ t('spaces.event') }}</span>
              <h2>{{ selected.title }}</h2>
              <p>{{ selected.status || t('common.status.unknown') }}</p>
            </div>
            <div class="detail-content">{{ selected.content }}</div>
            <div class="detail-toolbar">
              <button type="button" class="text-action" @click="openEditForm">
                {{ t('common.edit') }}
              </button>
            </div>
            <div class="detail-section">
              <h3>{{ t('spaces.notes') }}</h3>
              <span
                v-for="noteId in selected.note_ids || []"
                :key="noteId"
                class="id-chip"
                >Note #{{ noteId }}</span
              >
              <div v-if="!selected.note_ids?.length" class="detail-muted">
                {{ t('spaces.noNoteLinks') }}
              </div>
            </div>
            <div class="detail-section">
              <h3>{{ t('spaces.relations') }}</h3>
              <span
                v-for="relationId in selected.relation_ids || []"
                :key="relationId"
                class="id-chip"
                >Relation #{{ relationId }}</span
              >
              <div v-if="!selected.relation_ids?.length" class="detail-muted">
                {{ t('spaces.noRelations') }}
              </div>
              <div class="inline-action">
                <input
                  v-model="relationEventId"
                  inputmode="numeric"
                  :placeholder="t('spaces.otherEventId')"
                /><button
                  type="button"
                  class="text-action"
                  @click="addRelation"
                >
                  {{ t('spaces.addRelation') }}
                </button>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="detail-head">
              <span class="detail-kicker">{{ t('spaces.report') }}</span>
              <h2>{{ selected.title }}</h2>
              <p>{{ selected.status }} · {{ selected.body_format }}</p>
            </div>
            <div class="report-body">{{ selected.body }}</div>
            <div
              v-for="section in selected.sections || []"
              :key="section.id"
              class="report-section"
            >
              <h3>{{ section.title }}</h3>
              <div
                v-for="item in section.items || []"
                :key="item.id"
                class="report-item"
              >
                <strong>{{ item.title }}</strong>
                <p>{{ item.summary }}</p>
              </div>
            </div>
          </template>
        </aside>
      </main>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { spacesApi } from '@/api/spaces'

const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})
const { t } = useI18n()
const space = ref(null)
const activeTab = ref('notes')
const items = ref({ notes: [], events: [], reports: [] })
const selected = ref(null)
const loading = ref(false)
const detailLoading = ref(false)
const error = ref('')
const suggestions = ref([])
const formOpen = ref(false)
const formSubmitting = ref(false)
const formMode = ref('create')
const form = reactive({ kind: 'note', title: '', key: '', content: '' })
const evidenceMessageId = ref('')
const relationEventId = ref('')
const relationKind = ref('related')
const relationDecision = ref('pending')
const tabs = computed(() => [
  { value: 'notes', label: t('spaces.notes') },
  { value: 'events', label: t('spaces.events') },
  { value: 'reports', label: t('spaces.reports') }
])
const activeItems = computed(() => items.value[activeTab.value])
const activeLabel = computed(
  () => tabs.value.find((tab) => tab.value === activeTab.value)?.label
)
const activeDescription = computed(() => t(`spaces.${activeTab.value}Hint`))
const emptyTitle = computed(() =>
  t(`spaces.no${activeTab.value[0].toUpperCase()}${activeTab.value.slice(1)}`)
)
const emptyBody = computed(() =>
  t(
    `spaces.no${activeTab.value[0].toUpperCase()}${activeTab.value.slice(1)}Body`
  )
)
const listData = (response) => (response.data.data || response.data).list || []
const loadSpace = async () => {
  const response = await spacesApi.getSpaces()
  const data = response.data.data || response.data
  space.value =
    (Array.isArray(data) ? data : data.list || []).find(
      (item) => String(item.id) === String(props.spaceId)
    ) || null
}
const loadActive = async () => {
  loading.value = true
  error.value = ''
  try {
    const response =
      activeTab.value === 'notes'
        ? await spacesApi.getNotes(props.spaceId, { page_size: 100 })
        : activeTab.value === 'events'
          ? await spacesApi.getEvents(props.spaceId, { page_size: 100 })
          : await spacesApi.getReports(props.spaceId, { page_size: 100 })
    items.value[activeTab.value] = listData(response)
    if (activeTab.value === 'events') {
      const suggestionResponse = await spacesApi.getEventSuggestions(
        props.spaceId,
        { status: 'pending' }
      )
      suggestions.value =
        suggestionResponse.data.data || suggestionResponse.data || []
    }
    selected.value = null
    if (activeItems.value.length) selectItem(activeItems.value[0])
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    loading.value = false
  }
}
const reviewSuggestion = async (suggestion, decision) => {
  try {
    await spacesApi.reviewEventSuggestion(suggestion.id, decision)
    suggestions.value = suggestions.value.filter(
      (item) => item.id !== suggestion.id
    )
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  }
}
const selectItem = async (item) => {
  selected.value = item
  detailLoading.value = true
  try {
    const response =
      activeTab.value === 'notes'
        ? await spacesApi.getNote(item.id)
        : activeTab.value === 'events'
          ? await spacesApi.getEvent(item.id)
          : await spacesApi.getReport(item.id)
    selected.value = response.data.data || response.data
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    detailLoading.value = false
  }
}
const summaryFor = (item) =>
  item.content || item.summary || item.body?.slice(0, 100) || '—'
const metaFor = (item) =>
  item.status || item.origin || item.generated_at?.slice(0, 10) || ''
const formTitle = computed(() =>
  formMode.value === 'edit'
    ? t('spaces.editItem')
    : activeTab.value === 'notes'
      ? t('spaces.newNote')
      : activeTab.value === 'events'
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
const addEvidence = async () => {
  if (!selected.value || !evidenceMessageId.value) return
  try {
    await spacesApi.addNoteEvidence(selected.value.id, {
      message_id: Number(evidenceMessageId.value)
    })
    evidenceMessageId.value = ''
    await selectItem(selected.value)
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  }
}
const addRelation = async () => {
  if (!selected.value || !relationEventId.value) return
  try {
    await spacesApi.createEventRelation(props.spaceId, {
      left_event_id: selected.value.id,
      right_event_id: Number(relationEventId.value),
      relation_kind: relationKind.value,
      decision: relationDecision.value,
      source_note_ids: []
    })
    relationEventId.value = ''
    await selectItem(selected.value)
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  }
}
watch(activeTab, loadActive)
watch(
  () => props.spaceId,
  async () => {
    await loadSpace()
    await loadActive()
  }
)
onMounted(async () => {
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
  min-height: 100%;
  flex-direction: column;
  background: rgb(var(--c-bg));
  color: rgb(var(--c-tx));
}
.analysis-header {
  display: flex;
  min-height: 57px;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 10px 20px;
}
.analysis-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.analysis-back,
.analysis-switch {
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.analysis-back:hover,
.analysis-switch:hover {
  color: rgb(var(--c-ac));
}
.analysis-heading h1,
.detail-head h2 {
  margin: 0;
  font-size: 15px;
}
.analysis-heading p,
.detail-head p {
  margin: 3px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.analysis-alert {
  margin: 12px 20px 0;
  border: 1px solid rgb(var(--c-bad));
  border-radius: 6px;
  background: rgb(var(--c-bad-soft));
  padding: 9px 12px;
  color: rgb(var(--c-bad));
  font-size: 12px;
}
.analysis-tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 8px 20px 0;
}
.analysis-tab {
  border-bottom: 2px solid transparent;
  padding: 9px 12px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.analysis-tab span {
  margin-left: 5px;
  color: rgb(var(--c-tx3));
  font-family: ui-monospace, monospace;
  font-size: 10px;
}
.analysis-tab.active {
  border-bottom-color: rgb(var(--c-ac));
  color: rgb(var(--c-ac));
}
.analysis-actions {
  margin-left: auto;
}
.analysis-action {
  border: 1px solid rgb(var(--c-line));
  border-radius: 6px;
  padding: 7px 10px;
  color: rgb(var(--c-tx2));
  font-size: 11px;
}
.analysis-action:hover,
.analysis-action.primary {
  border-color: rgb(var(--c-ac));
  background: rgb(var(--c-ac));
  color: rgb(var(--c-ac-on));
}
.analysis-form {
  border-bottom: 1px solid rgb(var(--c-line));
  background: rgb(var(--c-panel-sub));
  padding: 14px 20px;
}
.analysis-form-head,
.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.analysis-form-head h2 {
  margin: 0;
  font-size: 13px;
}
.form-close,
.text-action {
  color: rgb(var(--c-ac));
  font-size: 11px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 10px;
}
.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: rgb(var(--c-tx2));
  font-size: 11px;
}
.form-grid input,
.form-grid textarea,
.inline-action input {
  border: 1px solid rgb(var(--c-line));
  border-radius: 5px;
  background: rgb(var(--c-panel));
  padding: 7px 8px;
  color: rgb(var(--c-tx));
  font-size: 12px;
  outline: none;
}
.form-grid textarea {
  resize: vertical;
}
.form-wide {
  grid-column: 1 / -1;
}
.form-actions {
  justify-content: flex-end;
  margin-top: 10px;
}
.detail-toolbar {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}
.inline-action {
  display: flex;
  gap: 7px;
  margin-top: 10px;
}
.inline-action input {
  width: 120px;
}
.relation-select {
  border: 1px solid rgb(var(--c-line));
  border-radius: 5px;
  background: rgb(var(--c-panel));
  padding: 6px;
  color: rgb(var(--c-tx2));
  font-size: 10px;
}
.suggestion-list {
  border-top: 1px solid rgb(var(--c-line-soft));
  padding: 15px 0;
}
.suggestion-list h3 {
  margin: 0 0 8px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.suggestion-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid rgb(var(--c-line-soft));
  padding: 8px 0;
}
.suggestion-row strong {
  color: rgb(var(--c-tx));
  font-size: 11px;
}
.suggestion-row p {
  margin: 3px 0 0;
  color: rgb(var(--c-tx2));
  font-size: 11px;
}
.analysis-body {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(300px, 0.85fr) minmax(340px, 1.4fr);
}
.analysis-list {
  min-width: 0;
  border-right: 1px solid rgb(var(--c-line));
}
.analysis-list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 14px 16px;
}
.analysis-list-head h2 {
  margin: 0;
  font-size: 14px;
}
.analysis-list-head p {
  margin: 4px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.analysis-refresh {
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.analysis-refresh:hover {
  color: rgb(var(--c-ac));
}
.analysis-items {
  overflow-y: auto;
  padding: 6px 8px;
}
.analysis-item {
  display: flex;
  width: 100%;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  border-radius: 7px;
  padding: 11px 9px;
  text-align: left;
}
.analysis-item:hover,
.analysis-item.active {
  background: rgb(var(--c-ac-soft));
}
.analysis-item-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}
.analysis-item-main strong {
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.analysis-item-main span {
  overflow: hidden;
  color: rgb(var(--c-tx2));
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.analysis-item-meta {
  flex: none;
  color: rgb(var(--c-tx3));
  font-size: 10px;
}
.analysis-detail {
  min-width: 0;
  overflow-y: auto;
  padding: 22px;
}
.detail-head {
  border-bottom: 1px solid rgb(var(--c-line));
  padding-bottom: 14px;
}
.detail-kicker {
  display: block;
  margin-bottom: 7px;
  color: rgb(var(--c-ac));
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.detail-content,
.report-body {
  white-space: pre-wrap;
  padding: 18px 0;
  color: rgb(var(--c-tx));
  font-size: 14px;
  line-height: 1.7;
}
.detail-section,
.report-section {
  border-top: 1px solid rgb(var(--c-line-soft));
  padding: 15px 0;
}
.detail-section h3,
.report-section h3 {
  margin: 0 0 9px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.evidence-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid rgb(var(--c-line-soft));
  padding: 7px 0;
  color: rgb(var(--c-tx2));
  font-size: 11px;
}
.evidence-row small,
.detail-muted {
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.id-chip {
  display: inline-block;
  margin: 0 5px 5px 0;
  border: 1px solid rgb(var(--c-line));
  border-radius: 999px;
  padding: 4px 7px;
  color: rgb(var(--c-tx2));
  font-family: ui-monospace, monospace;
  font-size: 10px;
}
.report-item {
  border-left: 2px solid rgb(var(--c-ac));
  padding: 4px 0 4px 11px;
}
.report-item + .report-item {
  margin-top: 10px;
}
.report-item strong {
  color: rgb(var(--c-tx));
  font-size: 12px;
}
.report-item p {
  margin: 5px 0 0;
  white-space: pre-wrap;
  color: rgb(var(--c-tx2));
  font-size: 12px;
  line-height: 1.6;
}
.analysis-state {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 28px 18px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.analysis-state strong {
  color: rgb(var(--c-tx2));
  font-size: 13px;
}
.detail-placeholder {
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}
@media (max-width: 768px) {
  .analysis-header {
    padding: 10px 14px;
  }
  .analysis-switch {
    display: none;
  }
  .analysis-body {
    display: flex;
    flex-direction: column;
  }
  .analysis-list {
    border-right: 0;
    border-bottom: 1px solid rgb(var(--c-line));
  }
  .analysis-items {
    max-height: 220px;
  }
  .analysis-detail {
    min-height: 360px;
    padding: 16px;
  }
}
</style>
