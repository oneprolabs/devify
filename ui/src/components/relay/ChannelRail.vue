<template>
  <div
    class="flex w-full flex-col gap-2 border-line bg-panel-sub p-3 md:w-[230px] md:flex-none md:border-r"
  >
    <label
      class="flex h-8 items-center gap-2 rounded-md border border-line bg-panel px-2.5"
    >
      <svg
        class="h-3.5 w-3.5 flex-none text-ink-3"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-4.5-4.5" stroke-linecap="round" />
      </svg>
      <input
        v-model="search"
        type="text"
        :placeholder="t('relay.searchChannels')"
        class="min-w-0 flex-1 border-0 bg-transparent p-0 text-xs text-ink placeholder:text-ink-3 focus:outline-none focus:ring-0"
      />
    </label>

    <template v-for="group in groups" :key="group.key">
      <div
        class="px-0.5 pt-1 font-mono text-[10.5px] tracking-[0.04em] text-ink-4"
      >
        {{ group.label }} · {{ group.channels.length }}
      </div>

      <button
        v-for="channel in group.channels"
        :key="channel.id"
        type="button"
        class="flex flex-col gap-[7px] rounded-[9px] border p-[11px] text-left transition-colors"
        :class="[
          String(channel.id) === String(selectedId)
            ? 'border-accent bg-accent-soft'
            : 'border-line bg-panel hover:border-ink-4',
          channel.enabled ? '' : 'opacity-65'
        ]"
        @click="$emit('select', channel)"
      >
        <span class="flex items-center gap-2">
          <span
            class="flex h-[22px] w-[22px] flex-none items-center justify-center rounded-md font-mono text-[8px] font-semibold"
            :class="
              String(channel.id) === String(selectedId)
                ? 'bg-panel text-accent'
                : 'bg-chip text-ink-2'
            "
          >
            {{ TYPE_INITIALS[channel.target_type] || '··' }}
          </span>
          <span
            class="min-w-0 truncate text-[12.5px] font-semibold"
            :class="
              String(channel.id) === String(selectedId)
                ? 'text-accent'
                : 'text-ink'
            "
          >
            {{ channel.name }}
          </span>
          <span
            class="ml-auto flex h-[17px] w-7 flex-none items-center rounded-full px-0.5 transition-colors"
            :class="channel.enabled ? 'justify-end bg-accent' : 'bg-chip'"
            role="switch"
            :aria-checked="channel.enabled"
            @click.stop="$emit('toggle', channel)"
          >
            <span
              class="h-[13px] w-[13px] rounded-full"
              :class="channel.enabled ? 'bg-accent-on' : 'bg-ink-4'"
            ></span>
          </span>
        </span>
        <span
          class="font-mono text-[10px]"
          :class="
            String(channel.id) === String(selectedId)
              ? 'text-accent opacity-80'
              : 'text-ink-4'
          "
        >
          {{ subtitle(channel) }}
        </span>
      </button>
    </template>

    <button
      type="button"
      class="mt-1 flex items-center gap-2 rounded-[9px] border border-dashed border-line px-[11px] py-2.5 text-[12.5px] text-ink-2 transition-colors hover:border-accent hover:text-accent"
      @click="$emit('create')"
    >
      <svg
        class="h-3.5 w-3.5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        aria-hidden="true"
      >
        <path d="M12 5v14M5 12h14" stroke-linecap="round" />
      </svg>
      {{ t('relay.addChannel') }}
    </button>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CHANNEL_CATEGORIES,
  TYPE_INITIALS,
  TYPE_LABEL_KEYS
} from './channelTypes'

const props = defineProps({
  channels: { type: Array, default: () => [] },
  selectedId: { type: [String, Number, null], default: null }
})

defineEmits(['select', 'toggle', 'create'])

const { t } = useI18n()
const search = ref('')

const matching = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return props.channels
  return props.channels.filter((channel) =>
    String(channel.name).toLowerCase().includes(term)
  )
})

// Grouped the way the type gallery groups them, so the two agree.
const groups = computed(() =>
  CHANNEL_CATEGORIES.map((category) => ({
    key: category.key,
    label: t(category.labelKey),
    channels: matching.value.filter((channel) =>
      category.types.includes(channel.target_type)
    )
  })).filter((group) => group.channels.length)
)

const subtitle = (channel) => {
  const type = t(TYPE_LABEL_KEYS[channel.target_type] || 'relay.targetFeishu')
  if (!channel.enabled) return `${type} · ${t('relay.channelDisabled')}`
  return `${type} · ${t('relay.deliveryCount', { count: channel.delivery_count || 0 })}`
}
</script>
