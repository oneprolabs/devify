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
vi.mock('@/composables/useAvatars', () => ({
  useAvatars: () => ({ resolve: (url) => (url ? 'blob:avatar' : '') })
}))
vi.mock('@/composables/useChatMedia', () => ({
  useChatMedia: () => ({ resolve: (url) => (url ? 'blob:media' : '') })
}))

const conversation = {
  id: 2,
  platform: 'wechat',
  title: '项目群',
  source_conversation_id: 'group-a',
  message_count: 1229,
  participant_count: 6,
  event_count: 5,
  pending_event_count: 3,
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
const event = {
  id: 9,
  title: '客户追问修复时间',
  content: '客户在群里第三次追问。',
  status: 'open',
  tags: [{ id: 1, label: '客户' }],
  last_activity_at: '2026-11-01T10:00:00Z'
}

describe('SpaceChats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    route.query = {}
    spacesApi.getConversations.mockResolvedValue({
      data: {
        data: {
          list: [conversation],
          counts: { total: 12, pending: 3 },
          pagination: { total: 12 }
        }
      }
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
          list: [event],
          pagination: { total: 5 }
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

  it('shows the rail filters, event counts and last-message preview', async () => {
    const wrapper = await mountPage()

    const filters = wrapper.findAll('.rail-head .seg button')
    expect(filters[0].text()).toContain('全部')
    expect(filters[0].text()).toContain('12')
    expect(filters[1].text()).toContain('有待处理')
    expect(filters[1].text()).toContain('3')
    expect(wrapper.text()).toContain('都乐：今天下午对齐一下')
    expect(wrapper.text()).toContain('5 个事件')
    expect(wrapper.text()).toContain('待处理')
  })

  it('opens the raw transcript first with sender avatars', async () => {
    const wrapper = await mountPage()

    expect(spacesApi.getMessages).toHaveBeenCalledWith('3', 2, {
      page_size: 100,
      page: 'last'
    })
    expect(spacesApi.getEvents).not.toHaveBeenCalled()
    expect(wrapper.find('.msg-av').text()).toBe('都')
    expect(wrapper.text()).toContain('今天下午对齐一下')
    expect(wrapper.text()).toContain('上面还有更早的消息')
    expect(wrapper.text()).toContain('云端 1229 条 · 6 人 · 5 个事件 · 待处理')
  })

  it('loads events only when the event tab opens', async () => {
    const wrapper = await mountPage()

    expect(spacesApi.getEvents).not.toHaveBeenCalled()
    expect(wrapper.findAll('.det-tabs button')[0].text()).toContain('5')

    await wrapper.findAll('.det-tabs button')[0].trigger('click')
    await flushPromises()

    expect(spacesApi.getEvents).toHaveBeenCalledWith('3', {
      conversation_id: 2,
      page_size: 100
    })
    expect(wrapper.text()).toContain('客户追问修复时间')
  })

  it('asks the API for conversations with pending events', async () => {
    const wrapper = await mountPage()

    await wrapper.findAll('.rail-head .seg button')[1].trigger('click')
    await flushPromises()

    expect(spacesApi.getConversations).toHaveBeenLastCalledWith('3', {
      page_size: 100,
      filter: 'pending'
    })
  })

  it('renders real avatars when the server provides them', async () => {
    spacesApi.getConversations.mockResolvedValue({
      data: {
        data: {
          list: [{ ...conversation, avatar_url: 'http://api/avatar/1' }],
          counts: { total: 1, pending: 3 },
          pagination: { total: 1 }
        }
      }
    })
    spacesApi.getMessages.mockResolvedValue({
      data: {
        data: {
          list: [
            {
              ...message,
              sender_avatar_url: 'http://api/avatar/2'
            }
          ],
          pagination: { page: 1 }
        }
      }
    })

    const wrapper = await mountPage()

    expect(wrapper.findAll('.conv-row img.av-img').length).toBe(1)
    expect(wrapper.findAll('.msg-av img.av-img').length).toBe(1)
    expect(wrapper.find('.msg-av').text()).toBe('')
  })

  it('renders an uploaded image in the expanded message', async () => {
    spacesApi.getMessage.mockResolvedValue({
      data: {
        data: {
          parts: [
            {
              id: 2,
              kind: 'image',
              binding_state: 'available',
              media_url: '/v1/spaces/3/media/42',
              media_content_type: 'image/png'
            }
          ]
        }
      }
    })

    const wrapper = await mountPage()
    await wrapper.find('.bub').trigger('click')
    await flushPromises()

    const image = wrapper.find('.part-image')
    expect(image.exists()).toBe(true)
  })

  it('keeps an honest empty state for the chat summary', async () => {
    const wrapper = await mountPage()

    await wrapper.findAll('.det-tabs button')[2].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('云端还没有为这个会话生成聊天总结')
  })

  it('filters the rail by search text', async () => {
    const wrapper = await mountPage()

    await wrapper.find('.rail-search input').setValue('对齐')
    expect(wrapper.text()).toContain('项目群')

    await wrapper.find('.rail-search input').setValue('不存在')
    expect(wrapper.text()).toContain('没有符合条件的会话')
  })
})
