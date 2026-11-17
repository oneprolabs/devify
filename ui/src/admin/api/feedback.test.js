// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { feedbackApi } from './feedback'
import api from '@/api/index'

vi.mock('@/api/index', () => ({
  default: { get: vi.fn() }
}))

const attachment = {
  id: 'image-1',
  download_path:
    '/api/v1/feedbacks/6f0f4f8e-1c7f-4b0e-9f5d-1f2b3c4d5e6f/attachments/7f0f4f8e-1c7f-4b0e-9f5d-1f2b3c4d5e6f'
}

describe('feedbackApi.fetchAttachment', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('rejects paths that are not attachment downloads', async () => {
    await expect(
      feedbackApi.fetchAttachment({ download_path: '/api/v1/other' })
    ).rejects.toThrow('附件地址无效。')
    expect(api.get).not.toHaveBeenCalled()
  })

  it('surfaces the server reason when the blob body is an error envelope', async () => {
    const body = new Blob([
      JSON.stringify({ code: 404, data: { detail: '附件已过期。' } })
    ])
    api.get.mockRejectedValue({ response: { status: 404, data: body } })

    await expect(feedbackApi.fetchAttachment(attachment)).rejects.toThrow(
      '附件已过期。'
    )
  })

  it('surfaces a DRF detail body without the unified envelope', async () => {
    api.get.mockRejectedValue({
      response: {
        status: 404,
        data: new Blob([JSON.stringify({ detail: 'Not found.' })])
      }
    })

    await expect(feedbackApi.fetchAttachment(attachment)).rejects.toThrow(
      'Not found.'
    )
  })

  it('keeps the network error when the blob body is not JSON', async () => {
    const original = new Error('Network Error')
    api.get.mockRejectedValue({
      response: { status: 502, data: new Blob(['bad gateway']) },
      message: original.message
    })

    await expect(feedbackApi.fetchAttachment(attachment)).rejects.toThrow(
      'Network Error'
    )
  })
})
