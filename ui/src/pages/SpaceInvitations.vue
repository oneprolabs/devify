<template>
  <AppLayout>
    <div class="simple-page">
      <PageHeader
        :title="t('spaces.invitations')"
        :description="t('spaces.invitationsHint')"
      />
      <div v-if="error" class="simple-alert" role="alert">{{ error }}</div>
      <div v-if="loading" class="simple-state">{{ t('common.loading') }}</div>
      <div v-else-if="!invitations.length" class="simple-state" role="status">
        <strong>{{ t('spaces.noInvitations') }}</strong
        ><span>{{ t('spaces.noInvitationsBody') }}</span>
      </div>
      <div v-else class="simple-list" role="list">
        <div
          v-for="invitation in invitations"
          :key="invitation.space_id"
          class="simple-row"
          role="listitem"
        >
          <div>
            <strong>{{ invitation.space_name }}</strong
            ><span>{{ invitation.role }} · {{ invitation.space_slug }}</span>
          </div>
          <div class="simple-actions">
            <button type="button" class="secondary" @click="reject(invitation)">
              {{ t('spaces.reject') }}</button
            ><button type="button" class="primary" @click="accept(invitation)">
              {{ t('spaces.accept') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { spacesApi } from '@/api/spaces'
const { t } = useI18n()
const invitations = ref([])
const loading = ref(false)
const error = ref('')
const load = async () => {
  loading.value = true
  try {
    const response = await spacesApi.getInvitations()
    invitations.value = response.data.data || response.data || []
  } catch (e) {
    error.value = e.response?.data?.detail || t('spaces.loadError')
  } finally {
    loading.value = false
  }
}
const accept = async (item) => {
  try {
    await spacesApi.acceptInvitation(
      item.space_id,
      item.invited_user_id || item.user_id
    )
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || t('spaces.loadError')
  }
}
const reject = async (item) => {
  try {
    await spacesApi.rejectInvitation(
      item.space_id,
      item.invited_user_id || item.user_id
    )
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || t('spaces.loadError')
  }
}
onMounted(load)
</script>
<style scoped>
.simple-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.simple-alert {
  border: 1px solid rgb(var(--c-bad));
  border-radius: 6px;
  background: rgb(var(--c-bad-soft));
  padding: 10px;
  color: rgb(var(--c-bad));
  font-size: 12px;
}
.simple-state {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 32px;
  color: rgb(var(--c-tx3));
  font-size: 12px;
}
.simple-state strong {
  color: rgb(var(--c-tx2));
  font-size: 13px;
}
.simple-list {
  border: 1px solid rgb(var(--c-line));
  border-radius: 10px;
  background: rgb(var(--c-panel));
  padding: 8px;
}
.simple-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgb(var(--c-line-soft));
  padding: 13px 10px;
}
.simple-row:last-child {
  border: 0;
}
.simple-row > div:first-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}
.simple-row strong {
  color: rgb(var(--c-tx));
  font-size: 13px;
}
.simple-row span {
  color: rgb(var(--c-tx3));
  font-size: 11px;
}
.simple-actions {
  display: flex;
  gap: 7px;
}
.primary,
.secondary {
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 11px;
}
.primary {
  background: rgb(var(--c-ac));
  color: rgb(var(--c-ac-on));
}
.secondary {
  border: 1px solid rgb(var(--c-line));
  color: rgb(var(--c-tx2));
}
</style>
