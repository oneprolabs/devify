<template>
  <PanelCard
    v-if="attachments.length"
    :title="t('chats.files.title')"
    :meta="String(attachments.length)"
  >
    <template #icon>
      <svg
        class="h-[15px] w-[15px] text-accent"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.9"
        aria-hidden="true"
      >
        <path
          d="M21 11l-8.5 8.5a5 5 0 01-7-7L14 4a3.5 3.5 0 015 5l-8.5 8.5a2 2 0 01-3-3L15 6"
          stroke-linecap="round"
        />
      </svg>
    </template>

    <!-- One row per file: type badge, name, size. Images swap the badge for
         their own thumbnail, which is the only preview the row can carry. -->
    <div class="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
      <button
        v-for="att in attachments"
        :key="att.id"
        type="button"
        class="flex items-center gap-[9px] rounded border border-line px-3 py-2.5 text-left transition-colors hover:border-ink-4"
        :title="att.filename"
        @click="onTileClick(att)"
      >
        <img
          v-if="isImage(att) && att.url"
          :src="att.url"
          :alt="att.filename"
          loading="lazy"
          class="h-[30px] w-[30px] flex-none rounded-md object-cover"
        />
        <span
          v-else
          class="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-md font-mono text-[9px] font-medium"
          :class="chipClass(att)"
        >
          {{ extLabel(att) }}
        </span>
        <span class="flex min-w-0 flex-col gap-px">
          <span class="truncate text-xs text-ink">{{ att.filename }}</span>
          <span
            v-if="att.file_size != null"
            class="font-mono text-[10px] text-ink-4"
          >
            {{ formatBytes(att.file_size) }}
          </span>
        </span>
        <a
          v-if="att.url"
          :href="att.url"
          :download="att.filename"
          class="ml-auto flex-none text-ink-4 transition-colors hover:text-accent"
          :title="t('chats.files.download')"
          @click.stop
        >
          <svg
            class="h-3.5 w-3.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </a>
      </button>
    </div>

    <!-- Preview modal (image or text) -->
    <Teleport to="body">
      <div
        v-if="preview"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
        @click="closePreview"
      >
        <img
          v-if="preview.type === 'image'"
          :src="preview.att.url"
          :alt="preview.att.filename"
          class="max-h-[90vh] max-w-[90vw] object-contain rounded shadow-xl"
          @click.stop
        />

        <div
          v-else
          class="flex w-full flex-col overflow-hidden rounded-lg bg-panel shadow-xl"
          :class="
            preview.type === 'pdf'
              ? 'max-w-5xl h-[90vh]'
              : 'max-w-3xl max-h-[85vh]'
          "
          @click.stop
        >
          <div class="flex items-center gap-2 border-b border-line px-4 py-2.5">
            <span class="flex-1 min-w-0 truncate text-sm font-medium text-ink">
              {{ preview.att.filename }}
            </span>
            <a
              :href="preview.att.url"
              :download="preview.att.filename"
              class="flex-none text-xs font-medium text-accent hover:text-accent"
            >
              {{ t('chats.files.download') }}
            </a>
            <button
              type="button"
              class="flex-none text-ink-4 hover:text-ink-2"
              :aria-label="t('common.close')"
              @click="closePreview"
            >
              <svg
                class="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
          <iframe
            v-if="preview.type === 'pdf'"
            :src="preview.att.url"
            :title="preview.att.filename"
            class="flex-1 w-full border-0"
          />
          <div v-else class="flex-1 overflow-auto p-4">
            <div v-if="preview.loading" class="text-sm text-ink-3 italic">
              {{ t('common.loading') }}
            </div>
            <div v-else-if="preview.error" class="text-sm text-bad">
              {{ preview.error }}
            </div>
            <pre
              v-else
              class="whitespace-pre-wrap break-words text-xs text-ink-2"
              >{{ preview.content }}</pre
            >
          </div>
        </div>

        <button
          v-if="preview.type === 'image'"
          type="button"
          class="absolute top-4 right-4 text-accent-on/80 hover:text-accent-on"
          :aria-label="t('common.close')"
          @click="closePreview"
        >
          <svg
            class="w-8 h-8"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </Teleport>
  </PanelCard>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import PanelCard from '@/components/ui/PanelCard.vue'
import { formatBytes } from '@/utils/formatting'

const { t } = useI18n()

defineProps({
  attachments: {
    type: Array,
    default: () => []
  }
})

const TEXT_CONTENT_TYPES = [
  'application/json',
  'application/xml',
  'application/x-yaml',
  'application/yaml',
  'application/x-sh'
]

// Extension -> colored chip. Lets Word/Excel/PDF/etc. read as intentional
// file types instead of a generic gray icon.
const TYPE_COLORS = {
  pdf: 'bg-bad-soft text-bad',
  doc: 'bg-accent-soft text-accent',
  docx: 'bg-accent-soft text-accent',
  xls: 'bg-ok-soft text-ok',
  xlsx: 'bg-ok-soft text-ok',
  csv: 'bg-ok-soft text-ok',
  ppt: 'bg-warn-soft text-warn',
  pptx: 'bg-warn-soft text-warn',
  zip: 'bg-warn-soft text-warn',
  rar: 'bg-warn-soft text-warn',
  '7z': 'bg-warn-soft text-warn'
}

const MAX_TEXT_PREVIEW = 100000

function isImage(att) {
  return (
    att.is_image || (att.content_type || '').toLowerCase().startsWith('image/')
  )
}

function isText(att) {
  const ct = (att.content_type || '').toLowerCase()
  return ct.startsWith('text/') || TEXT_CONTENT_TYPES.includes(ct)
}

function isPdf(att) {
  return (
    (att.content_type || '').toLowerCase() === 'application/pdf' ||
    ext(att) === 'pdf'
  )
}

// Full file extension (lowercased), used for type logic (isPdf, chipClass).
function ext(att) {
  const name = att.filename || ''
  const dot = name.lastIndexOf('.')
  if (dot >= 0 && dot < name.length - 1) {
    return name.slice(dot + 1).toLowerCase()
  }
  return ''
}

// Short label for the type chip; falls back to a generic "file" word.
function extLabel(att) {
  const e = ext(att)
  return e ? e.slice(0, 4) : t('chats.files.file')
}

function chipClass(att) {
  return TYPE_COLORS[ext(att)] || 'bg-chip text-ink-3'
}

// Unified preview modal state (image or text), null when closed
const preview = ref(null)

function onTileClick(att) {
  if (!att.url) return
  if (isImage(att)) {
    preview.value = { type: 'image', att }
  } else if (isPdf(att)) {
    preview.value = { type: 'pdf', att }
  } else if (isText(att)) {
    openTextPreview(att)
  } else {
    // Non-previewable (Word/Excel/PPT/archives): download instead
    triggerDownload(att)
  }
}

async function openTextPreview(att) {
  preview.value = {
    type: 'text',
    att,
    loading: true,
    error: '',
    content: ''
  }
  const state = preview.value
  try {
    // Request only the head of the file via a Range request so a huge
    // attachment is not fully buffered into memory just to show a preview.
    // nginx serves byte ranges on static files; if it ignores the header we
    // still cap the text below. Note: att.url is same-origin (relative) here;
    // a cross-origin ATTACHMENT_BASE_URL would need CORS for this fetch.
    const res = await fetch(att.url, {
      headers: { Range: `bytes=0-${MAX_TEXT_PREVIEW - 1}` }
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    let text = await res.text()
    if (text.length > MAX_TEXT_PREVIEW) {
      text = text.slice(0, MAX_TEXT_PREVIEW) + '\n…'
    }
    // Ignore if the modal was closed/switched while fetching
    if (preview.value !== state) return
    state.content = text
  } catch (e) {
    if (preview.value !== state) return
    state.error = t('chats.files.previewError')
  } finally {
    if (preview.value === state) state.loading = false
  }
}

// Relies on the anchor `download` attribute, which browsers honor only for
// same-origin URLs. att.url is relative/same-origin in this deployment; a
// cross-origin ATTACHMENT_BASE_URL would open the file in-tab instead of
// saving it and would need a blob-based download.
function triggerDownload(att) {
  const a = document.createElement('a')
  a.href = att.url
  a.download = att.filename || ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

function closePreview() {
  preview.value = null
}
</script>
