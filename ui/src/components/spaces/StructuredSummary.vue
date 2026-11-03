<template>
  <section
    v-if="groups.length"
    class="ws-sect ws-structured"
    :aria-labelledby="titleId"
  >
    <div class="ws-sectt">
      <span :id="titleId">{{ title }}</span>
      <span class="n">{{ itemCount }} 条</span>
      <span v-if="subtitle" class="aside">{{ subtitle }}</span>
    </div>
    <div class="ws-structured-grid">
      <article
        v-for="group in groups"
        :key="group.key"
        class="ws-structured-card"
        :class="`tone-${group.key}`"
      >
        <div class="ws-structured-card-head">
          <span class="ws-structured-dot" aria-hidden="true"></span>
          <h3>{{ group.label }}</h3>
          <span class="n">{{ group.items.length }}</span>
        </div>
        <ul>
          <li
            v-for="(item, index) in group.items"
            :key="`${group.key}-${index}`"
          >
            {{ item }}
          </li>
        </ul>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  entries: { type: Array, default: () => [] },
  title: { type: String, default: '结构化整理' },
  titleId: { type: String, default: 'structured-summary-title' },
  subtitle: { type: String, default: '' }
})

const groups = computed(() => {
  const definitions = [
    ['facts', '事实'],
    ['actions', '待办'],
    ['risks', '风险'],
    ['decisions', '决定']
  ]
  return definitions
    .map(([key, label]) => {
      const items = props.entries
        .flatMap((entry) => {
          const values = entry?.structured_data?.[key]
          return Array.isArray(values) ? values : []
        })
        .map((value) => {
          if (typeof value === 'string') return value.trim()
          if (!value || typeof value !== 'object') return ''
          return String(value.text || value.title || value.content || '').trim()
        })
        .filter(Boolean)
        .filter((item, index, all) => all.indexOf(item) === index)
      return { key, label, items }
    })
    .filter((group) => group.items.length)
})
const itemCount = computed(() =>
  groups.value.reduce((total, group) => total + group.items.length, 0)
)
</script>

<style scoped>
.ws-structured {
  gap: 12px;
}
.ws-structured-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.ws-structured-card {
  min-width: 0;
  border: 1px solid rgb(var(--c-line));
  border-radius: 9px;
  background: rgb(var(--c-panel));
  padding: 12px 14px;
}
.ws-structured-card-head {
  display: flex;
  align-items: center;
  gap: 7px;
  color: rgb(var(--c-tx2));
}
.ws-structured-card-head h3 {
  margin: 0;
  color: inherit;
  font-size: 12.5px;
  font-weight: 600;
}
.ws-structured-card-head .n {
  margin-left: auto;
}
.ws-structured-card ul {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 10px 0 0;
  padding: 0 0 0 17px;
  color: rgb(var(--c-tx2));
  font-size: 12.5px;
  line-height: 1.6;
}
.ws-structured-card li::marker {
  color: rgb(var(--c-tx3));
}
.ws-structured-dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: rgb(var(--c-tx3));
}
.tone-actions {
  border-color: rgb(var(--c-ac));
  background: rgb(var(--c-ac-soft));
}
.tone-actions .ws-structured-dot {
  background: rgb(var(--c-ac));
}
.tone-risks {
  border-color: rgb(var(--c-warn));
  background: rgb(var(--c-warn-soft));
}
.tone-risks .ws-structured-dot {
  background: rgb(var(--c-warn));
}
.tone-decisions {
  border-color: rgb(var(--c-ok));
  background: rgb(var(--c-ok-soft));
}
.tone-decisions .ws-structured-dot {
  background: rgb(var(--c-ok));
}
@media (max-width: 560px) {
  .ws-structured-grid {
    grid-template-columns: 1fr;
  }
}
</style>
