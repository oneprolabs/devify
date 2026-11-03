// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import EventWorkspace from './EventWorkspace.vue'
import { spacesApi } from '@/api/spaces'

vi.mock('@/api/spaces', () => ({
  spacesApi: {
    getEventNotes: vi.fn(),
    getEventTags: vi.fn(),
    createEventTag: vi.fn(),
    addEventTag: vi.fn(),
    removeEventTag: vi.fn()
  }
}))

const events = [
  { id: 1, title: '发布计划', content: '等待确认', status: 'open' },
  { id: 2, title: '完成文档', content: '已交付', status: 'done' }
]
const render = (props = {}) =>
  mount(EventWorkspace, {
    props: { spaceId: 1, events, ...props },
    global: { stubs: { RouterLink: true } }
  })

describe('EventWorkspace', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    spacesApi.getEventTags.mockResolvedValue({ data: { data: [] } })
    spacesApi.getEventNotes.mockResolvedValue({
      data: { data: { list: [], pagination: {} } }
    })
  })

  it('filters and searches loaded events and emits selection', async () => {
    const wrapper = render()
    await flushPromises()
    const segments = wrapper.findAll('.ws-seg button')
    expect(segments[0].text()).toContain('未完成')
    await segments[1].trigger('click')
    expect(wrapper.findAll('.ws-row')).toHaveLength(1)
    expect(wrapper.find('.ws-row').text()).toContain('完成文档')
    await wrapper.find('.ws-row').trigger('click')
    expect(wrapper.emitted('select')[0][0].id).toBe(2)
    await wrapper.find('input[type=search]').setValue('不存在')
    expect(wrapper.text()).toContain('没有符合条件的事件')
  })

  it('renders linked notes and their evidence, then opens the message', async () => {
    spacesApi.getEventNotes.mockResolvedValue({
      data: {
        data: {
          list: [
            {
              id: 3,
              title: '整理记录',
              content: '真实内容',
              origin: 'manual',
              evidence: [
                {
                  id: 4,
                  message_id: 44,
                  conversation_id: 9,
                  sender_name: '张卫震',
                  reference_key: 'ref-1'
                }
              ]
            }
          ],
          pagination: {}
        }
      }
    })
    const wrapper = render({ selected: { ...events[0], note_ids: [3] } })
    await flushPromises()
    expect(spacesApi.getEventNotes).toHaveBeenCalledWith(1, { page_size: 100 })
    expect(wrapper.text()).toContain('整理记录')
    expect(wrapper.text()).toContain('原文 1 条')
    await wrapper.find('.ws-evidence button').trigger('click')
    expect(wrapper.emitted('select-citation')[0][0]).toMatchObject({
      kind: 'message',
      id: 44,
      conversation_id: 9
    })
  })

  it('reports a linked note loading error', async () => {
    spacesApi.getEventNotes.mockRejectedValue(new Error('network'))
    const wrapper = render({ selected: { ...events[0], note_ids: [3] } })
    await flushPromises()
    expect(wrapper.find('[role=alert]').text()).toContain('加载失败')
  })

  it('emits a follow-up question instead of answering inline', async () => {
    const wrapper = render({ selected: { ...events[0], note_ids: [] } })
    await flushPromises()
    await wrapper.find('.ws-composer input').setValue('客户最早什么时候提的？')
    await wrapper.find('.ws-det-foot').trigger('submit')
    expect(wrapper.emitted('ask')[0][0]).toBe('客户最早什么时候提的？')
  })
})
