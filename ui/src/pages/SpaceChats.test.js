// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SpaceChats from './SpaceChats.vue'
import { spacesApi } from '@/api/spaces'

const route = { query: {} }

vi.mock('@/components/layout/AppLayout.vue', () => ({
  default: { template: '<div><slot /></div>' }
}))
vi.mock('@/api/spaces', () => ({
  spacesApi: {
    getConversations: vi.fn(),
    getMessages: vi.fn(),
    getMessage: vi.fn(),
    getEvents: vi.fn()
  }
}))
vi.mock('vue-router', () => ({
  useRoute: () => route
}))

const conversation = {
  id: 2,
  platform: 'wechat',
  title: '项目群',
  source_conversation_id: 'group-a',
  message_count: 1229,
  last_message_at: '2026-11-01T10:00:00Z',
  last_message_preview: '今天下午对齐一下',
  last_message_sender: '都乐'
}
const message = {
  id: 11,
  preview: '今天下午对齐一下',
  sender_name: '都乐',
  direction: 'incoming',
  occurred_at: '2026-11-01T10:00:00Z'
}

describe('SpaceChats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    route.query = {}
    spacesApi.getConversations.mockResolvedValue({
      data: { data: { list: [conversation], pagination: { total: 1 } } }
    })
    spacesApi.getMessages.mockResolvedValue({
      data: {
        data: {
          list: [message],
          pagination: { page: 13, previous: '/messages?page=12' }
        }
      }
    })
    spacesApi.getMessage.mockResolvedValue({
      data: {
        data: { parts: [{ id: 1, kind: 'text', text: '今天下午对齐一下' }] }
      }
    })
    spacesApi.getEvents.mockResolvedValue({
      data: {
        data: {
          list: [
            {
              id: 9,
              title: '客户追问修复时间',
              content: '客户在群里第三次追问。',
              status: 'open',
              tags: [{ id: 1, label: '客户' }],
              last_activity_at: '2026-11-01T10:00:00Z'
            }
          ],
          pagination: { total: 1 }
        }
      }
    })
  })

  const mountPage = async () => {
    const wrapper = mount(SpaceChats, {
      props: { spaceId: '3' },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } }
    })
    await flushPromises()
    return wrapper
  }

  it('shows the latest page and the last-message preview in the rail', async () => {
    const wrapper = await mountPage()

    expect(spacesApi.getMessages).toHaveBeenCalledWith('3', 2, {
      page_size: 100,
      page: 'last'
    })
    expect(wrapper.text()).toContain('都乐：今天下午对齐一下')
    expect(wrapper.text()).toContain('今天下午对齐一下')
    expect(wrapper.text()).toContain('上面还有更早的消息')
  })

  it('loads events for the selected conversation only when that tab opens', async () => {
    const wrapper = await mountPage()
    expect(spacesApi.getEvents).not.toHaveBeenCalled()

    await wrapper.findAll('.det-tabs button')[0].trigger('click')
    await flushPromises()

    expect(spacesApi.getEvents).toHaveBeenCalledWith('3', {
      conversation_id: 2,
      page_size: 100
    })
    expect(wrapper.text()).toContain('客户追问修复时间')
  })

  it('keeps an honest empty state for the chat summary', async () => {
    const wrapper = await mountPage()

    await wrapper.findAll('.det-tabs button')[2].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('云端还没有为这个会话生成聊天总结')
  })

  it('filters the rail by platform and search text', async () => {
    const wrapper = await mountPage()

    await wrapper.findAll('.rail-head .seg button')[2].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('没有符合条件的会话')

    await wrapper.findAll('.rail-head .seg button')[0].trigger('click')
    await wrapper.find('.rail-search input').setValue('对齐')
    expect(wrapper.text()).toContain('项目群')
  })
})
