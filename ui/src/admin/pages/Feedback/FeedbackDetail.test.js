// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FeedbackDetail from './FeedbackDetail.vue'
import { feedbackApi } from '@/admin/api/feedback'

vi.mock('@/admin/api/feedback', () => ({
  feedbackApi: { update: vi.fn(), download: vi.fn() }
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
  attachments: [{ id: 'image-1', expired: false }],
  context: {},
  diagnostics: {}
}

describe('feedback support handling', () => {
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
})
