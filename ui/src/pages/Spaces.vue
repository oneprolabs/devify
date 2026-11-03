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
            class="space-create"
            @click="showCreate = !showCreate"
          >
            {{ t('spaces.create') }}
          </button>
          <router-link to="/spaces/invitations" class="space-refresh">
            {{ t('spaces.invitations') }}
          </router-link>
          <router-link
            v-if="userStore.isAdmin"
            to="/spaces/admin"
            class="space-refresh"
          >
            {{ t('spaces.adminSpaces') }}
          </router-link>
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
      <form
        v-if="showCreate"
        class="space-create-form"
        @submit.prevent="createSpace"
      >
        <label
          ><span>{{ t('spaces.nameField') }}</span
          ><input v-model="createForm.name" required maxlength="120"
        /></label>
        <label
          ><span>{{ t('spaces.slugField') }}</span
          ><input v-model="createForm.slug" maxlength="140"
        /></label>
        <button type="submit" class="space-create" :disabled="actionLoading">
          {{ t('common.save') }}
        </button>
        <button type="button" class="space-cancel" @click="showCreate = false">
          {{ t('common.cancel') }}
        </button>
      </form>

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
          <router-link
            class="space-open-operations"
            :to="`/spaces/${selectedSpace.id}/operations`"
          >
            {{ t('spaces.openOperations') }}
          </router-link>

          <router-link
            class="space-open-operations"
            :to="`/spaces/${selectedSpace.id}/apps`"
          >
            {{ t('apps.centerTitle') }}
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
          <div class="quota-section">
            <div class="space-section-title"><h3>额度使用</h3><button type="button" class="space-refresh" @click="loadQuotaUsage">刷新</button></div>
            <div v-if="quotaUsage" class="quota-grid"><span>成员 {{ quotaUsage.member_count }}<small v-if="quota?.max_members"> / {{ quota.max_members }}</small></span><span>存储 {{ quotaUsage.storage_used_bytes }}<small v-if="quota?.storage_limit_bytes"> / {{ quota.storage_limit_bytes }}</small></span><span>AI {{ quotaUsage.daily_ai_calls_used }}<small v-if="quota?.daily_ai_calls"> / {{ quota.daily_ai_calls }}</small></span></div>
          </div>
          <div class="audit-section">
            <div class="space-section-title"><h3>操作记录</h3><span>{{ auditLogs.length }}</span></div>
            <div v-if="auditLoading" class="space-loading">{{ t('common.loading') }}</div>
            <div v-else-if="!auditLogs.length" class="space-empty compact"><span>暂无操作记录</span></div>
            <div v-else class="audit-list"><div v-for="log in auditLogs.slice(0, 8)" :key="log.id" class="audit-row"><strong>{{ log.action }}</strong><span>{{ log.actor || '系统' }} · {{ formatAuditDate(log.created_at) }}</span></div></div>
          </div>

          <div v-if="selectedSpace.kind === 'team'" class="management-section">
            <div class="space-section-title">
              <h3>{{ t('spaces.management') }}</h3>
              <span>{{ selectedSpace.role || '—' }}</span>
            </div>
            <div class="management-actions">
              <button
                v-if="canManage"
                type="button"
                class="space-action"
                @click="renameSpace"
              >
                {{ t('spaces.rename') }}
              </button>
              <button
                v-if="isOwner"
                type="button"
                class="space-action"
                @click="toggleArchive"
              >
                {{
                  selectedSpace.status === 'archived'
                    ? t('spaces.restore')
                    : t('spaces.archive')
                }}
              </button>
              <button
                v-if="isStaff"
                type="button"
                class="space-action"
                @click="toggleTakeover"
              >
                {{
                  takeoverActive
                    ? t('spaces.endTakeover')
                    : t('spaces.takeover')
                }}
              </button>
            </div>
            <div v-if="canManage" class="invite-form">
              <input
                v-model="inviteForm.userId"
                inputmode="numeric"
                :placeholder="t('spaces.userId')"
              />
              <select v-model="inviteForm.role">
                <option value="user">User</option>
                <option value="maintainer">Maintainer</option>
                <option value="guest">Guest</option>
              </select>
              <button
                type="button"
                class="space-action primary"
                @click="inviteMember"
              >
                {{ t('spaces.invite') }}
              </button>
            </div>
            <div v-if="membersLoading" class="space-loading">
              {{ t('common.loading') }}
            </div>
            <div v-else class="member-list">
              <div
                v-for="member in members"
                :key="member.user_id"
                class="member-row"
              >
                <div>
                  <strong>{{ member.username }}</strong
                  ><small>#{{ member.user_id }} · {{ member.status }}</small>
                </div>
                <div class="member-actions">
                  <select
                    v-if="canManage && member.role !== 'owner'"
                    :value="member.role"
                    @change="changeRole(member, $event.target.value)"
                  >
                    <option value="maintainer">Maintainer</option>
                    <option value="user">User</option>
                    <option value="guest">Guest</option>
                  </select>
                  <span v-else class="member-role">{{ member.role }}</span>
                  <button
                    v-if="isOwner && member.role !== 'owner'"
                    type="button"
                    class="text-danger"
                    @click="transferOwnership(member)"
                  >
                    {{ t('spaces.transfer') }}
                  </button>
                  <button
                    v-if="canManage && member.role !== 'owner'"
                    type="button"
                    class="text-danger"
                    @click="removeMember(member)"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
              </div>
              <div v-if="!members.length" class="space-empty compact">
                <strong>{{ t('spaces.noMembers') }}</strong
                ><span>{{ t('spaces.noMembersBody') }}</span>
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
import { useUserStore } from '@/store/user'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { spacesApi } from '@/api/spaces'

const { t } = useI18n()
const userStore = useUserStore()
const spaces = ref([])
const sources = ref([])
const selectedId = ref(
  Number(localStorage.getItem('devify.activeSpaceId')) || null
)
const loading = ref(false)
const sourcesLoading = ref(false)
const error = ref('')
const members = ref([])
const auditLogs = ref([])
const quotaUsage = ref(null)
const quota = ref(null)
const auditLoading = ref(false)
const membersLoading = ref(false)
const actionLoading = ref(false)
const showCreate = ref(false)
const createForm = ref({ name: '', slug: '' })
const inviteForm = ref({ userId: '', role: 'user' })

const canManage = computed(() =>
  ['owner', 'maintainer'].includes(selectedSpace.value?.role)
)
const isOwner = computed(() => selectedSpace.value?.role === 'owner')
const isStaff = computed(() => Boolean(userStore.isAdmin))
const takeoverActive = computed(() =>
  Boolean(selectedSpace.value?.admin_takeover_active)
)

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

const loadQuotaUsage = async () => { try { const response = await spacesApi.getQuotaUsage(selectedSpace.value.id); const data = response.data.data || response.data; quotaUsage.value = data.usage; quota.value = data.quota } catch { quotaUsage.value = null } }
const loadAuditLogs = async () => {
  if (!selectedSpace.value) { auditLogs.value = []; return }
  auditLoading.value = true
  try { const response = await spacesApi.getAuditLogs(selectedSpace.value.id); const data = response.data.data || response.data || []
    auditLogs.value = Array.isArray(data) ? data : data.list || [] } catch { auditLogs.value = [] } finally { auditLoading.value = false }
}
const formatAuditDate = value => value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''
const loadMembers = async () => {
  if (!selectedSpace.value || selectedSpace.value.kind !== 'team') return
  membersLoading.value = true
  try {
    const response = await spacesApi.getMembers(selectedSpace.value.id)
    members.value = response.data.data || response.data || []
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    membersLoading.value = false
  }
}

const runAction = async (action) => {
  actionLoading.value = true
  try {
    await action()
    await loadSpaces()
    await loadMembers()
    await loadAuditLogs()
    await loadQuotaUsage()
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || t('spaces.loadError')
  } finally {
    actionLoading.value = false
  }
}
const createSpace = () =>
  runAction(async () => {
    await spacesApi.createSpace(createForm.value)
    showCreate.value = false
    createForm.value = { name: '', slug: '' }
  })
const renameSpace = () => {
  const name = window.prompt(t('spaces.nameField'), selectedSpace.value.name)
  if (name && name !== selectedSpace.value.name)
    runAction(() => spacesApi.updateSpace(selectedSpace.value.id, { name }))
}
const toggleArchive = () => {
  const next = selectedSpace.value.status === 'archived' ? 'active' : 'archived'
  if (window.confirm(t('spaces.confirmArchive')))
    runAction(() =>
      spacesApi.updateSpace(selectedSpace.value.id, { status: next })
    )
}
const toggleTakeover = () => {
  if (takeoverActive.value) {
    if (window.confirm(t('spaces.confirmEndTakeover')))
      runAction(() => spacesApi.endTakeover(selectedSpace.value.id))
  } else {
    const reason = window.prompt(
      t('spaces.takeoverReason'),
      t('spaces.supportInvestigation')
    )
    if (reason)
      runAction(() => spacesApi.takeoverSpace(selectedSpace.value.id, reason))
  }
}
const inviteMember = () => {
  if (!inviteForm.value.userId) return
  runAction(() =>
    spacesApi.inviteMember(selectedSpace.value.id, {
      user_id: Number(inviteForm.value.userId),
      role: inviteForm.value.role
    })
  )
}
const changeRole = (member, role) => {
  if (window.confirm(t('spaces.confirmRole')))
    runAction(() =>
      spacesApi.updateMember(selectedSpace.value.id, member.user_id, { role })
    )
}
const removeMember = (member) => {
  if (window.confirm(t('spaces.confirmRemove')))
    runAction(() =>
      spacesApi.removeMember(selectedSpace.value.id, member.user_id)
    )
}
const transferOwnership = (member) => {
  if (window.confirm(t('spaces.confirmTransfer')))
    runAction(() =>
      spacesApi.transferOwnership(selectedSpace.value.id, member.user_id)
    )
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

watch(selectedId, async () => {
  await loadSources()
  await loadMembers()
    await loadAuditLogs()
  await loadQuotaUsage()
})
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
.space-open-operations {
  display: inline-flex;
  margin: 14px 16px 0;
  border: 1px solid rgb(var(--c-line));
  border-radius: 6px;
  padding: 8px 11px;
  color: rgb(var(--c-tx2));
  font-size: 12px;
}
.space-open-operations:hover {
  border-color: rgb(var(--c-ac));
  color: rgb(var(--c-ac));
}
.management-section {
  border-top: 1px solid rgb(var(--c-line));
  margin-top: 14px;
}
.management-actions,
.invite-form,
.member-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  padding: 0 16px 10px;
}
.space-action,
.space-cancel {
  border: 1px solid rgb(var(--c-line));
  border-radius: 5px;
  padding: 6px 9px;
  color: rgb(var(--c-tx2));
  font-size: 11px;
}
.space-action:hover {
  border-color: rgb(var(--c-ac));
  color: rgb(var(--c-ac));
}
.space-action.primary {
  border-color: rgb(var(--c-ac));
  background: rgb(var(--c-ac));
  color: rgb(var(--c-ac-on));
}
.text-danger {
  color: rgb(var(--c-bad));
  font-size: 10px;
}
.invite-form input,
.invite-form select,
.member-actions select {
  width: 110px;
  border: 1px solid rgb(var(--c-line));
  border-radius: 5px;
  background: rgb(var(--c-panel));
  padding: 6px 7px;
  color: rgb(var(--c-tx));
  font-size: 11px;
}
.member-list {
  padding: 0 8px 8px;
}
.member-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-top: 1px solid rgb(var(--c-line-soft));
  padding: 9px 8px;
}
.member-row > div:first-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}
.member-row strong {
  color: rgb(var(--c-tx));
  font-size: 12px;
}
.member-row small {
  color: rgb(var(--c-tx3));
  font-size: 10px;
}
.member-role {
  color: rgb(var(--c-tx3));
  font-size: 10px;
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
.quota-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:14px; }.quota-grid span { border:1px solid rgb(var(--c-line-soft)); padding:8px; font-size:11px; }.quota-grid small { color:rgb(var(--c-tx3)); }.audit-list { border-top:1px solid rgb(var(--c-line-soft)); }.audit-row { display:flex; justify-content:space-between; gap:10px; border-bottom:1px solid rgb(var(--c-line-soft)); padding:8px 0; font-size:11px; }.audit-row span { color:rgb(var(--c-tx3)); }.space-detail-placeholder strong {
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
