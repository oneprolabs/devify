<template>
  <AppLayout>
    <div class="space-page">
      <PageHeader
        :title="t('spaces.title')"
        :description="t('spaces.subtitle')"
      >
        <template #actions>
          <button
            type="button"
            class="space-refresh"
            :disabled="loading"
            @click="loadSpaces"
          >
            {{ t('common.refresh') }}
          </button>
        </template>
      </PageHeader>

      <div v-if="error" class="space-alert" role="alert">{{ error }}</div>

      <div class="space-grid">
        <section class="space-panel" aria-labelledby="space-list-title">
          <div class="space-panel-head">
            <div>
              <h2 id="space-list-title">{{ t('spaces.available') }}</h2>
              <p>{{ t('spaces.availableHint') }}</p>
            </div>
            <span class="space-count">{{ spaces.length }}</span>
          </div>

          <div v-if="loading" class="space-loading" aria-busy="true">
            {{ t('common.loading') }}
          </div>
          <div v-else-if="!spaces.length" class="space-empty" role="status">
            <strong>{{ t('spaces.emptyTitle') }}</strong>
            <span>{{ t('spaces.emptyBody') }}</span>
          </div>
          <div v-else class="space-list" role="list">
            <button
              v-for="space in spaces"
              :key="space.id"
              type="button"
              class="space-row"
              :class="{ active: space.id === selectedSpace?.id }"
              role="listitem"
              @click="selectSpace(space)"
            >
              <span class="space-mark" :class="space.kind">
                {{ space.kind === 'team' ? 'T' : 'P' }}
              </span>
              <span class="space-row-copy">
                <strong>{{ space.name }}</strong>
                <small>{{ space.kind }} · {{ space.status }}</small>
              </span>
              <span v-if="space.role" class="space-role">{{ space.role }}</span>
            </button>
          </div>
        </section>

        <section
          v-if="selectedSpace"
          class="space-panel"
          aria-labelledby="space-detail-title"
        >
          <div class="space-panel-head">
            <div>
              <h2 id="space-detail-title">{{ selectedSpace.name }}</h2>
              <p>{{ t('spaces.sourcesHint') }}</p>
            </div>
            <span class="space-status">{{ selectedSpace.status }}</span>
          </div>

          <div class="space-summary">
            <div>
              <span>{{ t('spaces.type') }}</span
              ><strong>{{ selectedSpace.kind }}</strong>
            </div>
            <div>
              <span>{{ t('spaces.role') }}</span
              ><strong>{{ selectedSpace.role || '—' }}</strong>
            </div>
            <div>
              <span>{{ t('spaces.sources') }}</span
              ><strong>{{ sources.length }}</strong>
            </div>
          </div>
          <router-link
            class="space-open-workspace"
            :to="`/spaces/${selectedSpace.id}/chats`"
          >
            {{ t('spaces.openWorkspace') }}
          </router-link>
          <router-link
            class="space-open-analysis"
            :to="`/spaces/${selectedSpace.id}/analysis`"
          >
            {{ t('spaces.openAnalysis') }}
          </router-link>

          <div class="space-section-title">
            <h3>{{ t('spaces.sources') }}</h3>
            <span>{{ t('spaces.capabilitiesNote') }}</span>
          </div>
          <div v-if="sourcesLoading" class="space-loading">
            {{ t('common.loading') }}
          </div>
          <div
            v-else-if="!sources.length"
            class="space-empty compact"
            role="status"
          >
            <strong>{{ t('spaces.noSources') }}</strong>
            <span>{{ t('spaces.noSourcesBody') }}</span>
          </div>
          <div v-else class="source-list" role="list">
            <div
              v-for="source in sources"
              :key="source.id"
              class="source-row"
              role="listitem"
            >
              <div class="source-copy">
                <strong>{{ source.display_name }}</strong>
                <span
                  >{{ source.channel_type }} · {{ source.provider }} ·
                  {{ source.status }}</span
                >
              </div>
              <div class="source-capabilities">
                <span
                  v-for="capability in source.capabilities"
                  :key="capability"
                  >{{ capability }}</span
                >
                <em v-if="!source.capabilities.length">{{
                  t('spaces.noCapabilities')
                }}</em>
              </div>
            </div>
          </div>
        </section>

        <section
          v-else
          class="space-panel space-detail-placeholder"
          role="status"
        >
          <strong>{{ t('spaces.selectTitle') }}</strong>
          <span>{{ t('spaces.selectBody') }}</span>
        </section>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { spacesApi } from '@/api/spaces'

const { t } = useI18n()
const spaces = ref([])
const sources = ref([])
const selectedId = ref(
  Number(localStorage.getItem('devify.activeSpaceId')) || null
)
const loading = ref(false)
const sourcesLoading = ref(false)
const error = ref('')

const selectedSpace = computed(
  () => spaces.value.find((space) => space.id === selectedId.value) || null
)

const selectSpace = (space) => {
  selectedId.value = space.id
  localStorage.setItem('devify.activeSpaceId', String(space.id))
}

const loadSources = async () => {
  if (!selectedSpace.value) {
    sources.value = []
    return
  }
  sourcesLoading.value = true
  try {
    const response = await spacesApi.getSources(selectedSpace.value.id)
    const data = response.data.data || response.data
    sources.value = data.sources || []
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    sourcesLoading.value = false
  }
}

const loadSpaces = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await spacesApi.getSpaces()
    const data = response.data.data || response.data
    spaces.value = Array.isArray(data) ? data : data.list || []
    if (!selectedSpace.value && spaces.value.length)
      selectSpace(spaces.value[0])
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    loading.value = false
  }
}

watch(selectedId, loadSources)
onMounted(loadSpaces)
</script>

<style scoped>
.space-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.space-refresh {
  border: 1px solid rgb(var(--c-line));
  border-radius: 6px;
  padding: 7px 12px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.space-refresh:hover {
  border-color: rgb(var(--c-tx3));
  color: rgb(var(--c-tx));
}
.space-refresh:disabled {
  cursor: wait;
  opacity: 0.55;
}
.space-alert {
  border: 1px solid rgb(var(--c-bad));
  border-radius: 6px;
  background: rgb(var(--c-bad-soft));
  padding: 10px 12px;
  color: rgb(var(--c-bad));
  font-size: 13px;
}
.space-grid {
  display: grid;
  grid-template-columns: minmax(260px, 0.8fr) minmax(0, 1.4fr);
  gap: 16px;
}
.space-panel {
  min-width: 0;
  border: 1px solid rgb(var(--c-line));
  border-radius: 10px;
  background: rgb(var(--c-panel));
}
.space-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgb(var(--c-line));
  padding: 16px;
}
.space-panel-head h2 {
  margin: 0;
  color: rgb(var(--c-tx));
  font-size: 16px;
}
.space-panel-head p {
  margin: 5px 0 0;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.space-count,
.space-status {
  color: rgb(var(--c-tx3));
  font-family: ui-monospace, monospace;
  font-size: 11px;
}
.space-status {
  border-radius: 999px;
  background: rgb(var(--c-ok-soft));
  padding: 4px 8px;
  color: rgb(var(--c-ok));
}
.space-list,
.source-list {
  padding: 8px;
}
.space-row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 10px;
  border-radius: 7px;
  padding: 11px 9px;
  text-align: left;
}
.space-row:hover,
.space-row.active {
  background: rgb(var(--c-ac-soft));
}
.space-mark {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 6px;
  background: rgb(var(--c-chip));
  color: rgb(var(--c-tx2));
  font-family: ui-monospace, monospace;
  font-size: 11px;
}
.space-mark.team {
  background: rgb(var(--c-ac-soft));
  color: rgb(var(--c-ac));
}
.space-row-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 3px;
}
.space-row-copy strong,
.source-copy strong {
  overflow: hidden;
  color: rgb(var(--c-tx));
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.space-row-copy small,
.source-copy span {
  color: rgb(var(--c-tx3));
  font-size: 11px;
  text-transform: capitalize;
}
.space-role {
  color: rgb(var(--c-tx3));
  font-size: 10px;
}
.space-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  border-bottom: 1px solid rgb(var(--c-line));
  background: rgb(var(--c-line));
}
.space-summary div {
  display: flex;
  flex-direction: column;
  gap: 5px;
  background: rgb(var(--c-panel));
  padding: 12px 16px;
}
.space-summary span,
.space-section-title span {
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.space-summary strong {
  color: rgb(var(--c-tx));
  font-family: ui-monospace, monospace;
  font-size: 12px;
  text-transform: capitalize;
}
.space-open-workspace {
  display: inline-flex;
  margin: 14px 16px 0;
  border-radius: 6px;
  background: rgb(var(--c-ac));
  padding: 8px 11px;
  color: rgb(var(--c-ac-on));
  font-size: 12px;
}
.space-open-workspace:hover {
  opacity: 0.9;
}
.space-open-analysis {
  display: inline-flex;
  margin: 14px 16px 0;
  border: 1px solid rgb(var(--c-line));
  border-radius: 6px;
  padding: 8px 11px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.space-open-analysis:hover {
  border-color: rgb(var(--c-ac));
  color: rgb(var(--c-ac));
}
.space-section-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 16px 8px;
}
.space-section-title h3 {
  margin: 0;
  color: rgb(var(--c-tx));
  font-size: 13px;
}
.source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid rgb(var(--c-line-soft));
  padding: 12px 8px;
}
.source-row:last-child {
  border-bottom: 0;
}
.source-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}
.source-capabilities {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 5px;
}
.source-capabilities span {
  border: 1px solid rgb(var(--c-line));
  border-radius: 999px;
  padding: 3px 7px;
  color: rgb(var(--c-tx2));
  font-size: 10px;
}
.source-capabilities em {
  color: rgb(var(--c-tx4));
  font-size: 11px;
  font-style: normal;
}
.space-loading,
.space-empty {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 28px 18px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.space-empty strong,
.space-detail-placeholder strong {
  color: rgb(var(--c-tx2));
  font-size: 13px;
}
.space-empty.compact {
  padding: 22px 16px;
}
.space-detail-placeholder {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  text-align: center;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
@media (max-width: 768px) {
  .space-grid {
    grid-template-columns: 1fr;
  }
  .space-summary {
    grid-template-columns: repeat(3, 1fr);
  }
  .source-row {
    align-items: flex-start;
    flex-direction: column;
  }
  .source-capabilities {
    justify-content: flex-start;
  }
}
</style>
