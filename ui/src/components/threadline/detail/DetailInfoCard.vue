<template>
  <PanelCard :title="t('metadata.sectionTitle')" dense>
    <div class="flex flex-col gap-[9px]">
      <div class="flex gap-3">
        <span class="w-[52px] flex-none text-[calc(11.5px*var(--fs))] text-ink-3">
          {{ t('chats.from') }}
        </span>
        <span class="truncate text-[calc(11.5px*var(--fs))] text-ink" :title="threadline.sender">
          {{ threadline.sender || t('common.noData') }}
        </span>
      </div>

      <div class="flex gap-3">
        <span class="w-[52px] flex-none text-[calc(11.5px*var(--fs))] text-ink-3">
          {{ t('chats.detail.receivedAt') }}
        </span>
        <span class="font-mono text-[calc(11px*var(--fs))] text-ink">
          {{ formatDate(threadline.received_at || threadline.created_at) }}
        </span>
      </div>

      <div v-if="threadline.metadata" class="flex gap-3">
        <span class="w-[52px] flex-none pt-0.5 text-[calc(11.5px*var(--fs))] text-ink-3">
          {{ t('metadata.category.title') }}
        </span>
        <MetadataChipsEditor
          :model-value="threadline.metadata.category || ''"
          variant="blue"
          :disabled="saving('category')"
          :loading="saving('category')"
          @update:model-value="(value) => emit('change', 'category', value)"
          @change="(value) => emit('save', 'category', value)"
        />
      </div>

      <div v-if="threadline.metadata" class="flex gap-3">
        <span class="w-[52px] flex-none pt-0.5 text-[calc(11.5px*var(--fs))] text-ink-3">
          {{ t('metadata.participants.title') }}
        </span>
        <MetadataChipsEditor
          :model-value="threadline.metadata.participants || []"
          variant="green"
          :max-display="6"
          :disabled="saving('participants')"
          :loading="saving('participants')"
          @update:model-value="(value) => emit('change', 'participants', value)"
          @change="(value) => emit('save', 'participants', value)"
        />
      </div>
    </div>
  </PanelCard>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import PanelCard from '@/components/ui/PanelCard.vue'
import MetadataChipsEditor from '@/components/MetadataChipsEditor.vue'

defineProps({
  threadline: { type: Object, required: true },
  formatDate: { type: Function, required: true },
  saving: { type: Function, required: true }
})

const emit = defineEmits(['change', 'save'])

const { t } = useI18n()
</script>
