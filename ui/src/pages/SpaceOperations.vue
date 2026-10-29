<template>
  <AppLayout :padded="false">
    <div class="operations-page">
      <header class="operations-header">
        <div class="operations-heading">
          <router-link
            :to="`/spaces/${spaceId}/analysis`"
            class="operations-back"
            >{{ t('common.back') }}</router-link
          >
          <div>
            <h1>{{ space?.name || t('spaces.title') }}</h1>
            <p>{{ t('spaces.operationsWorkspace') }}</p>
          </div>
        </div>
        <router-link to="/spaces" class="operations-switch">{{
          t('spaces.switchSpace')
        }}</router-link>
      </header>
      <div v-if="error" class="operations-alert" role="alert">{{ error }}</div>
      <nav class="operations-tabs" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.value"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }} <span>{{ items.length }}</span>
        </button>
      </nav>
      <main class="operations-list">
        <div class="operations-list-head">
          <div>
            <h2>{{ activeLabel }}</h2>
            <p>{{ activeDescription }}</p>
          </div>
          <label v-if="activeTab === 'uploads'" class="upload-button">
            {{ uploading ? t('spaces.uploading') : t('spaces.uploadPackage') }}
            <input
              type="file"
              accept=".zip,application/zip"
              :disabled="uploading"
              @change="uploadPackage"
            />
          </label>
          <button
            type="button"
            class="operations-refresh"
            :disabled="loading"
            @click="loadActive"
          >
            {{ t('common.refresh') }}
          </button>
        </div>
        <div v-if="loading" class="operations-state" aria-busy="true">
          {{ t('common.loading') }}
        </div>
        <div v-else-if="!items.length" class="operations-state" role="status">
          <strong>{{ t('spaces.noOperations') }}</strong
          ><span>{{ t('spaces.noOperationsBody') }}</span>
        </div>
        <div v-else class="operation-rows" role="list">
          <div
            v-for="item in items"
            :key="item.id"
            class="operation-row"
            role="listitem"
          >
            <div class="operation-main">
              <strong>{{ titleFor(item) }}</strong
              ><span>{{ detailFor(item) }}</span>
            </div>
            <span
              class="operation-status"
              :class="statusClass(item.status || item.state)"
              >{{ item.status || item.state }}</span
            ><button
              v-if="
                activeTab === 'jobs' &&
                ['failed', 'partial'].includes(item.state)
              "
              type="button"
              class="operation-retry"
              @click="retry(item)"
            >
              {{ t('common.tryAgain') }}
            </button>
          </div>
        </div>
      </main>
    </div>
  </AppLayout>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { spacesApi } from '@/api/spaces'
const props = defineProps({
  spaceId: { type: [String, Number], required: true }
})
const { t } = useI18n()
const space = ref(null)
const activeTab = ref('uploads')
const items = ref([])
const loading = ref(false)
const uploading = ref(false)
const error = ref('')
const tabs = computed(() => [
  { value: 'uploads', label: t('spaces.uploads') },
  { value: 'jobs', label: t('spaces.analysisJobs') }
])
const activeLabel = computed(
  () => tabs.value.find((tab) => tab.value === activeTab.value)?.label
)
const activeDescription = computed(() => t(`spaces.${activeTab.value}Hint`))
const listData = (response) => (response.data.data || response.data).list || []
const loadSpace = async () => {
  const response = await spacesApi.getSpaces()
  const data = response.data.data || response.data
  space.value =
    (Array.isArray(data) ? data : data.list || []).find(
      (entry) => String(entry.id) === String(props.spaceId)
    ) || null
}
const loadActive = async () => {
  loading.value = true
  error.value = ''
  try {
    const response =
      activeTab.value === 'uploads'
        ? await spacesApi.getUploads(props.spaceId, { page_size: 100 })
        : await spacesApi.getAnalysisJobs(props.spaceId, { page_size: 100 })
    items.value = listData(response)
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    loading.value = false
  }
}
const titleFor = (item) =>
  activeTab.value === 'uploads'
    ? `${item.source_type} · ${item.source_account_id || t('spaces.unknownSource')}`
    : item.request_key
const detailFor = (item) =>
  activeTab.value === 'uploads'
    ? `${item.message_count} ${t('spaces.messages')} · ${item.duplicate_count} ${t('spaces.duplicates')}`
    : `${item.input_version} · ${item.attempts} ${t('spaces.attempts')}`
const statusClass = (status) =>
  ({
    completed: 'ok',
    ready: 'ok',
    success: 'ok',
    failed: 'bad',
    partial: 'warn',
    processing: 'warn',
    running: 'warn'
  })[status] || ''
const retry = async (item) => {
  try {
    await spacesApi.retryAnalysisJob(item.id)
    await loadActive()
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  }
}
const uploadPackage = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || uploading.value) return
  uploading.value = true
  error.value = ''
  try {
    const created = await spacesApi.createUpload(props.spaceId, {
      source_type: 'wechat',
      idempotency_key: `web-${Date.now()}-${file.name}`,
      archive_size: file.size
    })
    const batch = created.data.data || created.data
    await spacesApi.uploadArchive(batch.id, file)
    await spacesApi.completeUpload(batch.id)
    await loadActive()
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    uploading.value = false
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
.operations-page {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  background: rgb(var(--c-bg));
  color: rgb(var(--c-tx));
}
.operations-header {
  display: flex;
  min-height: 57px;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 10px 20px;
}
.operations-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.operations-back,
.operations-switch {
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.operations-back:hover,
.operations-switch:hover {
  color: rgb(var(--c-ac));
}
.operations-heading h1 {
  margin: 0;
  font-size: 15px;
}
.operations-heading p {
  margin: 3px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.operations-alert {
  margin: 12px 20px 0;
  border: 1px solid rgb(var(--c-bad));
  border-radius: 6px;
  background: rgb(var(--c-bad-soft));
  padding: 9px 12px;
  color: rgb(var(--c-bad));
  font-size: 12px;
}
.operations-tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 8px 20px 0;
}
.operations-tabs button {
  border-bottom: 2px solid transparent;
  padding: 9px 12px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.operations-tabs button.active {
  border-bottom-color: rgb(var(--c-ac));
  color: rgb(var(--c-ac));
}
.operations-tabs span {
  margin-left: 5px;
  color: rgb(var(--c-tx3));
  font-family: ui-monospace, monospace;
  font-size: 10px;
}
.operations-list {
  width: min(960px, 100%);
  min-width: 0;
  margin: 0 auto;
  flex: 1;
  padding: 20px;
}
.operations-list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding-bottom: 14px;
}
.operations-list-head h2 {
  margin: 0;
  font-size: 15px;
}
.operations-list-head p {
  margin: 4px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.operations-refresh,
.operation-retry {
  color: rgb(var(--c-ac));
  font-size: 11px;
}
.upload-button {
  position: relative;
  border: 1px solid rgb(var(--c-ac));
  border-radius: 6px;
  padding: 7px 10px;
  color: rgb(var(--c-ac));
  cursor: pointer;
  font-size: 11px;
}
.upload-button input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}
.operation-rows {
  padding-top: 6px;
}
.operation-row {
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgb(var(--c-line-soft));
  padding: 13px 4px;
}
.operation-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 4px;
}
.operation-main strong {
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.operation-main span {
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.operation-status {
  border-radius: 999px;
  background: rgb(var(--c-chip));
  padding: 4px 8px;
  color: rgb(var(--c-tx2));
  font-family: ui-monospace, monospace;
  font-size: 10px;
}
.operation-status.ok {
  background: rgb(var(--c-ok-soft));
  color: rgb(var(--c-ok));
}
.operation-status.warn {
  background: rgb(var(--c-warn-soft));
  color: rgb(var(--c-warn));
}
.operation-status.bad {
  background: rgb(var(--c-bad-soft));
  color: rgb(var(--c-bad));
}
.operations-state {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 32px 4px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.operations-state strong {
  color: rgb(var(--c-tx2));
  font-size: 13px;
}
@media (max-width: 768px) {
  .operations-header {
    padding: 10px 14px;
  }
  .operations-switch {
    display: none;
  }
  .operations-list {
    padding: 16px 14px;
  }
  .operation-row {
    align-items: flex-start;
  }
  .operation-status {
    flex: none;
  }
}
</style>
