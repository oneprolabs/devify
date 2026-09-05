import { computed, unref } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePreferencesStore } from '@/store/preferences'
import { formatDate } from '@/utils/timezone'
import { getThreadlineDisplayStatus } from '@/utils/threadlineStatus'

/**
 * The display fields a chat list row shows, derived once so the desktop row
 * and the phone card cannot drift apart.
 *
 * `source` accepts a threadline or a getter returning one.
 */
export function useChatRowFields(source) {
  const { t } = useI18n()
  const preferences = usePreferencesStore()

  const chat = computed(() =>
    typeof source === 'function' ? source() : unref(source)
  )

  const status = computed(() => getThreadlineDisplayStatus(chat.value))

  const percent = computed(() => {
    if (status.value !== 'processing' && status.value !== 'retrying') {
      return null
    }

    const snapshot =
      chat.value?.processing_progress ||
      chat.value?.metadata?.processing_progress
    const value = Number(snapshot?.percent ?? snapshot?.progress_percent)

    if (!Number.isFinite(value)) {
      return 0
    }

    // 100% with the row still processing reads as finished, so hold at 99.
    return Math.min(99, Math.max(0, Math.round(value)))
  })

  const title = computed(
    () =>
      chat.value?.summary_title ||
      chat.value?.subject ||
      `Email #${chat.value?.id}`
  )

  const preview = computed(
    () => stripMarkdown(chat.value) || t('chats.noSummary')
  )

  const senderName = computed(() => {
    const sender = chat.value?.sender
    if (!sender) return t('common.noData')
    if (typeof sender === 'string') return displayName(sender)
    return sender.name || sender.email || sender.address || t('common.noData')
  })

  const attachmentCount = computed(
    () => chat.value?.attachments_count ?? chat.value?.attachments?.length ?? 0
  )

  const source_ = computed(() =>
    attachmentCount.value
      ? `${senderName.value} · ${t('chats.attachmentsShort', { count: attachmentCount.value })}`
      : senderName.value
  )

  // The canvas leans on recency: today and yesterday get named, older rows
  // fall back to a month-day stamp. Nothing here shows a year.
  const time = computed(() => {
    const raw = chat.value?.received_at || chat.value?.created_at
    if (!raw) return ''

    const zone = preferences.currentTimezone
    const language = preferences.currentLanguage
    const clock = formatDate(raw, zone, 'HH:mm', language)
    const stamp = formatDate(raw, zone, 'yyyy-MM-dd', language)
    const today = formatDate(new Date(), zone, 'yyyy-MM-dd', language)
    const yesterday = formatDate(
      new Date(Date.now() - 24 * 60 * 60 * 1000),
      zone,
      'yyyy-MM-dd',
      language
    )

    if (stamp === today) return `${t('common.today')} ${clock}`
    if (stamp === yesterday) return `${t('common.yesterday')} ${clock}`
    return `${stamp.slice(5)} ${clock}`
  })

  const mergedCount = computed(() => chat.value?.merged_children_count || 0)
  const shared = computed(
    () =>
      Boolean(chat.value?.share_status?.is_active) &&
      !chat.value?.share_status?.is_expired
  )
  const tags = computed(() => chat.value?.metadata?.keywords || [])

  return {
    status,
    percent,
    title,
    preview,
    senderName,
    source: source_,
    time,
    mergedCount,
    shared,
    tags
  }
}

function displayName(sender) {
  const match = sender.match(/^\s*"?([^"<]+?)"?\s*<[^>]+>\s*$/)
  return match ? match[1] : sender
}

function stripMarkdown(chat) {
  const content =
    chat?.summary_content ||
    chat?.text_content ||
    chat?.preview ||
    chat?.llm_content ||
    ''

  if (typeof content !== 'string') return String(content)

  return content
    .replace(/```[\s\S]*?```/g, '')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^[*+-]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/^---+$/gm, '')
    .replace(/[*`]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}
