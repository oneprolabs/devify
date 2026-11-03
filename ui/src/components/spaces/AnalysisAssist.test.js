// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AnalysisAssist from './AnalysisAssist.vue'
import { spacesApi } from '@/api/spaces'
vi.mock('@/api/spaces', () => ({ spacesApi: { getTopics: vi.fn(), getQuestions: vi.fn().mockResolvedValue({ data: { data: [] } }), createTopic: vi.fn(), askQuestion: vi.fn(), deleteTopic: vi.fn() } }))
describe('AnalysisAssist', () => {
  beforeEach(() => vi.resetAllMocks())
  it('loads real topics and asks with the selected event scope', async () => {
    spacesApi.getTopics.mockResolvedValue({ data: { data: [{ id: 1, title: '客户风险', instruction: '总结风险' }] } })
    spacesApi.askQuestion.mockResolvedValue({ data: { data: { answer: '有一个风险。', citations: [{ kind: 'event', id: 7, title: '风险', excerpt: '等待确认' }], scope: { event_ids: [7] } } } })
    const wrapper = mount(AnalysisAssist, { props: { spaceId: 3, selectedEvent: { id: 7, title: '风险' } } })
    await flushPromises()
    // The assist panel starts collapsed; the forms only exist once expanded.
    await wrapper.find('button.assist-toggle').trigger('click')
    expect(wrapper.text()).toContain('客户风险')
    await wrapper.find('textarea[placeholder*="当前还有哪些"]').setValue('当前风险是什么')
    await wrapper.find('form.question-form').trigger('submit')
    await flushPromises()
    expect(spacesApi.askQuestion).toHaveBeenCalledWith(3, { question: '当前风险是什么', event_ids: [7] })
    expect(wrapper.text()).toContain('有一个风险。')
  })
  it('creates a topic through the API instead of local-only state', async () => {
    spacesApi.getTopics.mockResolvedValue({ data: { data: [] } })
    spacesApi.createTopic.mockResolvedValue({ data: { data: { id: 2, title: '交付', instruction: '总结交付' } } })
    const wrapper = mount(AnalysisAssist, { props: { spaceId: 3 } })
    await flushPromises()
    await wrapper.find('button.assist-toggle').trigger('click')
    await wrapper.find('button.link-button').trigger('click')
    await wrapper.find('input[placeholder*="客户风险"]').setValue('交付')
    await wrapper.find('textarea[placeholder*="希望如何"]').setValue('总结交付')
    await wrapper.find('form.topic-form').trigger('submit')
    await flushPromises()
    expect(spacesApi.createTopic).toHaveBeenCalledWith(3, expect.objectContaining({ title: '交付', instruction: '总结交付' }))
    expect(wrapper.text()).toContain('交付')
  })
})
