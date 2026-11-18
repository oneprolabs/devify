// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FeedbackDetail from './FeedbackDetail.vue'
import { feedbackApi } from '@/admin/api/feedback'

vi.mock('@/admin/api/feedback', () => ({
  feedbackApi: { update: vi.fn(), fetchAttachment: vi.fn() }
}))

const report = {
  id: 'report-1',
  submitted_by: 'user',
  description: '上传失败',
  contact: '',
  status: 'received',
  reply: '',
  fix_version: '',
  assigned_to: null,
  attachments: [],
  context: {},
  diagnostics: {}
}

const reportWithImage = {
  ...report,
  attachments: [
    {
      id: 'image-1',
      size: 1024,
      mime_type: 'image/png',
      expired: false,
      download_path:
        '/api/v1/feedbacks/6f0f4f8e-1c7f-4b0e-9f5d-1f2b3c4d5e6f/attachments/7f0f4f8e-1c7f-4b0e-9f5d-1f2b3c4d5e6f'
    }
  ]
}

describe('feedback support handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:preview-1')
    globalThis.URL.revokeObjectURL = vi.fn()
  })

  it('saves the support reply and fix version on the selected report', async () => {
    feedbackApi.update.mockResolvedValue({
      ...report,
      status: 'resolved',
      reply: '已修复',
      fix_version: '0.1.1'
    })
    const wrapper = mount(FeedbackDetail, { props: { report } })
    await wrapper.get('select').setValue('resolved')
    await wrapper.get('textarea').setValue('已修复')
    await wrapper.get('input[maxlength="64"]').setValue('0.1.1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(feedbackApi.update).toHaveBeenCalledWith('report-1', {
      status: 'resolved',
      reply: '已修复',
      fix_version: '0.1.1',
      assigned_to: null
    })
    expect(wrapper.emitted('updated')[0][0].reply).toBe('已修复')
    wrapper.unmount()
  })

  it('does not show success when saving fails and keeps the reply editable', async () => {
    feedbackApi.update.mockRejectedValue(new Error('offline'))
    const wrapper = mount(FeedbackDetail, { props: { report } })
    await wrapper.get('textarea').setValue('处理中')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.get('textarea').element.value).toBe('处理中')
    wrapper.unmount()
  })

  it('previews the screenshot inline instead of forcing a download', async () => {
    feedbackApi.fetchAttachment.mockResolvedValue(new Blob(['image']))
    const wrapper = mount(FeedbackDetail, {
      props: { report: reportWithImage }
    })
    await flushPromises()

    const thumbnail = wrapper.get('button[aria-label="查看截图 1"]')
    expect(thumbnail.element.disabled).toBe(false)
    expect(wrapper.get('img[alt="反馈截图 1"]').attributes('src')).toBe(
      'blob:preview-1'
    )

    await thumbnail.trigger('click')
    expect(
      wrapper.find('[role="dialog"][aria-label="截图预览"]').exists()
    ).toBe(true)

    const closeButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '关闭')
    await closeButton.trigger('click')
    expect(
      wrapper.find('[role="dialog"][aria-label="截图预览"]').exists()
    ).toBe(false)
    wrapper.unmount()
  })

  it('marks expired screenshots and never requests them', async () => {
    const wrapper = mount(FeedbackDetail, {
      props: {
        report: {
          ...report,
          attachments: [{ ...reportWithImage.attachments[0], expired: true }]
        }
      }
    })
    await flushPromises()
    expect(feedbackApi.fetchAttachment).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('附件已过期')
    wrapper.unmount()
  })

  it('does not report a preview error for thumbnails still queued', async () => {
    let releaseFirst
    feedbackApi.fetchAttachment
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            releaseFirst = () => resolve(new Blob(['a']))
          })
      )
      .mockResolvedValue(new Blob(['b']))
    const wrapper = mount(FeedbackDetail, {
      props: {
        report: {
          ...report,
          attachments: [
            reportWithImage.attachments[0],
            { ...reportWithImage.attachments[0], id: 'image-2' }
          ]
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('预览加载失败')
    expect(wrapper.text()).toContain('加载中')

    releaseFirst()
    await flushPromises()
    expect(wrapper.findAll('img[alt^="反馈截图"]')).toHaveLength(2)
    wrapper.unmount()
  })

  it('retries a screenshot preview that failed to load', async () => {
    feedbackApi.fetchAttachment
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue(new Blob(['image']))
    const wrapper = mount(FeedbackDetail, {
      props: { report: reportWithImage }
    })
    await flushPromises()

    const thumbnail = wrapper.get('button[aria-label="查看截图 1"]')
    expect(thumbnail.text()).toContain('offline')
    expect(thumbnail.element.disabled).toBe(false)

    await thumbnail.trigger('click')
    await flushPromises()

    expect(feedbackApi.fetchAttachment).toHaveBeenCalledTimes(2)
    expect(wrapper.get('img[alt="反馈截图 1"]').attributes('src')).toBe(
      'blob:preview-1'
    )
    wrapper.unmount()
  })

  it('returns focus to the thumbnail after closing the preview', async () => {
    feedbackApi.fetchAttachment.mockResolvedValue(new Blob(['image']))
    const wrapper = mount(FeedbackDetail, {
      props: { report: reportWithImage },
      attachTo: document.body
    })
    await flushPromises()

    const thumbnail = wrapper.get('button[aria-label="查看截图 1"]')
    thumbnail.element.focus()
    expect(document.activeElement).toBe(thumbnail.element)

    await thumbnail.trigger('click')
    await flushPromises()
    expect(document.activeElement?.textContent.trim()).toBe('关闭')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(document.activeElement).toBe(thumbnail.element)
    wrapper.unmount()
  })

  it('renders text diagnostics as lines and keeps legacy JSON readable', async () => {
    const lines = [
      '2026-11-18T17:00:00.000+08:00\tERROR\tupload.failure\tmethod=POST url=https://devify.test/api/v1/x status=503'
    ]
    const wrapper = mount(FeedbackDetail, {
      props: {
        report: {
          ...report,
          context: { app_version: '0.1.9' },
          diagnostics: {
            schema_version: 2,
            generated_at: '2026-11-18T09:00:00Z',
            lines
          }
        }
      }
    })
    await flushPromises()
    expect(wrapper.text()).toContain(lines[0])
    wrapper.unmount()

    const legacy = mount(FeedbackDetail, {
      props: {
        report: {
          ...report,
          diagnostics: {
            schema_version: 1,
            generated_at: '2026-11-13T09:00:00Z',
            events: [{ at: '2026-11-13T09:00:00Z', module: 'upload' }]
          }
        }
      }
    })
    await flushPromises()
    expect(legacy.text()).toContain('"schema_version": 1')
    legacy.unmount()
  })

  it('stops queued previews after the component unmounts', async () => {
    let releaseFirst
    feedbackApi.fetchAttachment.mockImplementation(
      () =>
        new Promise((resolve) => {
          releaseFirst = () => resolve(new Blob(['a']))
        })
    )
    const wrapper = mount(FeedbackDetail, {
      props: {
        report: {
          ...report,
          attachments: [
            reportWithImage.attachments[0],
            { ...reportWithImage.attachments[0], id: 'image-2' }
          ]
        }
      }
    })
    await flushPromises()
    expect(feedbackApi.fetchAttachment).toHaveBeenCalledTimes(1)

    wrapper.unmount()
    releaseFirst()
    await flushPromises()

    expect(feedbackApi.fetchAttachment).toHaveBeenCalledTimes(1)
  })
})
