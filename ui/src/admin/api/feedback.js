import api from '@/api/index'
import { extractResponseData } from '@/utils/api'

export const feedbackApi = {
  list(params) {
    return api.get('/v1/admin/feedbacks', { params }).then(extractResponseData)
  },
  update(id, data) {
    return api
      .patch(`/v1/admin/feedbacks/${id}`, data)
      .then(extractResponseData)
  },
  async download(attachment) {
    if (
      !/^\/api\/v1\/feedbacks\/[a-f0-9-]{36}\/attachments\/[a-f0-9-]{36}$/.test(
        attachment.download_path || ''
      )
    ) {
      throw new Error('附件下载地址无效。')
    }
    const response = await api.get(
      attachment.download_path.replace(/^\/api/, ''),
      { responseType: 'blob' }
    )
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `screenshot-${attachment.id}.png`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
