export const validCount = (value) =>
  (typeof value === 'number' ||
    (typeof value === 'string' && value.trim() !== '')) &&
  Number.isSafeInteger(Number(value)) &&
  Number(value) >= 0

export const formatDate = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

export const eventStatusText = (status) =>
  ({ open: '未完成', in_progress: '进行中', done: '已完成' })[status] ||
  '待确认'

export const uploadStatusText = (status) =>
  ({
    created: '已创建',
    uploading: '上传中',
    completed: '已完成',
    processing: '解析中',
    pending: '排队中',
    failed: '失败',
    cancelled: '已取消'
  })[status] ||
  status ||
  '待确认'

export const eventSource = (event) => {
  const labels = (event.tags || []).map((tag) => tag.label).filter(Boolean)
  return labels.length ? labels.slice(0, 2).join(' · ') : '云端记录'
}
