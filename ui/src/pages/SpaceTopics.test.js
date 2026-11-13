// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SpaceTopics from './SpaceTopics.vue'
import { spacesApi } from '@/api/spaces'

vi.mock('@/api/spaces', () => ({
  spacesApi: {
    getTopics: vi.fn(),
    getEvents: vi.fn(),
    getTopicReports: vi.fn(),
    createTopic: vi.fn(),
    deleteTopic: vi.fn(),
    runTopic: vi.fn()
  }
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

const topics = [
  {
    id: 4,
    title: '客户交付风险',
    instruction: '关注交付节点和客户反馈。',
    period: 'week',
    time_local: '09:00:00',
    timezone: 'Asia/Shanghai',
    enabled: true,
    filters: {}
  }
]
const events = [
  { id: 1, title: '英文版交付', content: '周五前', status: 'open' }
]
const render = () =>
  mount(SpaceTopics, {
    props: { spaceId: 3 },
    global: {
      stubs: {
        AppLayout: { template: '<div><slot /></div>' }
      }
    }
  })

describe('SpaceTopics', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    spacesApi.getTopics.mockResolvedValue({ data: { data: topics } })
    spacesApi.getEvents.mockResolvedValue({
      data: { data: { list: events, pagination: {} } }
    })
    spacesApi.getTopicReports.mockResolvedValue({ data: { data: [] } })
  })

  it('renders the split rail and the selected topic detail', async () => {
    const wrapper = render()
    await flushPromises()
    expect(wrapper.find('.ws-rail').text()).toContain('1 个 · 1 个运行中')
    expect(wrapper.find('.ws-display').text()).toBe('客户交付风险')
    expect(wrapper.text()).toContain('关注交付节点和客户反馈。')
    expect(wrapper.text()).toContain('每周')
    expect(wrapper.text()).toContain('英文版交付')
  })

  it('runs a topic and prepends the new report', async () => {
    spacesApi.runTopic.mockResolvedValue({
      data: { data: { id: 99, title: '客户交付风险', status: 'queued' } }
    })
    const wrapper = render()
    await flushPromises()
    const button = wrapper
      .findAll('.ws-det-actions button')
      .find((item) => item.text().includes('立即生成报告'))
    await button.trigger('click')
    await flushPromises()
    expect(spacesApi.runTopic).toHaveBeenCalledWith(4)
    expect(wrapper.text()).toContain('查看报告')
  })

  it('creates a topic from the detail form', async () => {
    spacesApi.createTopic.mockResolvedValue({ data: { data: topics[0] } })
    const wrapper = render()
    await flushPromises()
    await wrapper.find('.ws-rail-action').trigger('click')
    const inputs = wrapper.findAll('.topic-form input')
    await inputs[0].setValue('新的主题')
    await wrapper.find('.topic-form textarea').setValue('关注新内容。')
    await wrapper.find('.topic-form').trigger('submit')
    await flushPromises()
    expect(spacesApi.createTopic).toHaveBeenCalledWith(
      3,
      expect.objectContaining({ title: '新的主题', period: 'week' })
    )
  })
})
