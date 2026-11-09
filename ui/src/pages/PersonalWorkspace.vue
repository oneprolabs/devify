<template>
  <AppLayout>
    <div v-if="error" role="alert" class="space-y-3 text-sm text-ink-2">
      <p>{{ t('spaces.personalWorkspaceError') }}</p>
      <button type="button" class="text-accent" @click="openWorkspace">{{ t('common.refresh') }}</button>

    </div>
    <p v-else aria-busy="true" class="text-sm text-ink-3">{{ t('common.loading') }}</p>
  </AppLayout>
</template>
<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { spacesApi } from '@/api/spaces'
const router = useRouter()
const route = useRoute()
let requestId = 0
const { t } = useI18n()
const error = ref(false)
async function openWorkspace() {
  const current = ++requestId
  const view = route.query.view === 'chats' ? 'chats' : 'analysis'
  error.value = false
  try {
    const response = await spacesApi.getSpaces()
    const data = response.data.data || response.data
    const personal = (Array.isArray(data) ? data : data.list || []).find(space => space.kind === 'personal' && space.is_personal_owner)
    if (current !== requestId) return
    if (!personal) throw new Error('No personal space')
    await router.replace(`/spaces/${personal.id}/${view === 'analysis' ? 'overview' : 'chats'}`)
  } catch {
    if (current === requestId) error.value = true
  }
}
watch(() => route.query.view, openWorkspace, { immediate: true })
</script>
