import api from '@/api/index'
import { extractResponseData } from '@/utils/api'

const ATTACHMENT_PATH =
  /^\/api\/v1\/feedbacks\/[a-f0-9-]{36}\/attachments\/[a-f0-9-]{36}$/

// Attachment downloads use responseType 'blob', so a DRF error body also
// arrives as a Blob and extractErrorMessage cannot read it. Decode it back to
// JSON so the user sees the server's reason (expired, missing, forbidden).
async function normalizeBlobError(error) {
  const data = error?.response?.data
  if (typeof Blob === 'undefined' || !(data instanceof Blob)) return error
  try {
    const body = JSON.parse(await data.text())
    const detail = body?.data?.detail || body?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return new Error(detail.trim())
    }
  } catch {
    // Not JSON: fall back to the original network error.
  }
  return error
}

export const feedbackApi = {
  list(params) {
    return api.get('/v1/admin/feedbacks', { params }).then(extractResponseData)
  },
  update(id, data) {
    return api
      .patch(`/v1/admin/feedbacks/${id}`, data)
      .then(extractResponseData)
  },
  async fetchAttachment(attachment) {
    if (!ATTACHMENT_PATH.test(attachment.download_path || '')) {
      throw new Error('附件地址无效。')
    }
    try {
      const response = await api.get(
        attachment.download_path.replace(/^\/api/, ''),
        { responseType: 'blob' }
      )
      return response.data
    } catch (error) {
      throw await normalizeBlobError(error)
    }
  }
}
