<template>
  <PanelCard :title="t('metadata.keywords.title')" dense>
    <MetadataChipsEditor
      :model-value="keywords"
      variant="gray"
      :max-display="12"
      :disabled="saving"
      :loading="saving"
      @update:model-value="(value) => emit('change', value)"
      @change="(value) => emit('save', value)"
    />
  </PanelCard>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import PanelCard from '@/components/ui/PanelCard.vue'
import MetadataChipsEditor from '@/components/MetadataChipsEditor.vue'

const props = defineProps({
  threadline: { type: Object, required: true },
  saving: { type: Boolean, default: false }
})

const emit = defineEmits(['change', 'save'])

const { t } = useI18n()

const keywords = computed(() => props.threadline?.metadata?.keywords || [])
</script>
