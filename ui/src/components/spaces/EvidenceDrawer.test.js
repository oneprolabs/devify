// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import EvidenceDrawer from './EvidenceDrawer.vue'
import { spacesApi } from '@/api/spaces'

vi.mock('@/api/spaces', () => ({
  spacesApi: {
    getConversation: vi.fn(),
    getMessages: vi.fn(),
    getNote: vi.fn(),
    getEvent: vi.fn(),
    getEventNotes: vi.fn()
  }
}))
vi.mock('@/composables/useChatMedia', () => ({
  useChatMedia: () => ({ resolve: (url) => (url ? 'blob:media' : '') })
}))

const render = (target) =>
  mount(EvidenceDrawer, { props: { spaceId: 1, target } })

describe('EvidenceDrawer', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    spacesApi.getEventNotes.mockResolvedValue({
      data: { data: { list: [], pagination: {} } }
    })
    spacesApi.getConversation.mockResolvedValue({
      data: { data: { id: 9, title: '客户群' } }
    })
  })

  it('previews a note and drills into its evidence', async () => {
    spacesApi.getNote.mockResolvedValue({
      data: {
        data: {
          id: 3,
          title: '周报整理',
          content: '客户确认下周交付',
          origin: 'auto',
          evidence: [
            {
              id: 1,
              message_id: 44,
              conversation_id: 9,
              sender_name: '张卫震'
            }
          ],
          event_ids: [5]
        }
      }
    })
    const wrapper = render({ kind: 'note', id: 3 })
    await flushPromises()

    expect(spacesApi.getNote).toHaveBeenCalledWith(3)
    expect(wrapper.find('.ev-title').text()).toBe('周报整理')
    expect(wrapper.text()).toContain('客户确认下周交付')

    await wrapper.find('.ev-row').trigger('click')
    expect(wrapper.emitted('navigate')[0][0]).toMatchObject({
      kind: 'message',
      id: 44,
      conversation_id: 9
    })
  })

  it('previews an event with its notes and evidence', async () => {
    spacesApi.getEvent.mockResolvedValue({
      data: {
        data: {
          id: 5,
          title: '发布风险',
          status: 'open',
          content: '等待客户确认',
          evidence: [
            {
              id: 2,
              message_id: 44,
              conversation_id: 9,
              sender_name: 'Alice'
            }
          ]
        }
      }
    })
    spacesApi.getEventNotes.mockResolvedValue({
      data: {
        data: {
          list: [{ id: 3, title: '整理记录' }],
          pagination: {}
        }
      }
    })
    const wrapper = render({ kind: 'event', id: 5 })
    await flushPromises()

    expect(spacesApi.getEvent).toHaveBeenCalledWith(5)
    expect(spacesApi.getEventNotes).toHaveBeenCalledWith(5, { page_size: 20 })
    expect(wrapper.find('.ev-title').text()).toBe('发布风险')
    expect(wrapper.text()).toContain('整理记录')

    await wrapper.find('.ev-row').trigger('click')
    expect(wrapper.emitted('navigate')[0][0]).toMatchObject({
      kind: 'note',
      id: 3
    })
  })

  it('opens the raw conversation focused on the cited message', async () => {
    spacesApi.getMessages.mockResolvedValue({
      data: {
        data: {
          list: [
            {
              id: 44,
              preview: '明天确认报价',
              sender_name: 'Alice',
              occurred_at: '2026-11-04T02:00:00Z',
              direction: 'incoming'
            },
            {
              id: 45,
              preview: '收到',
              sender_name: 'Bob',
              occurred_at: '2026-11-04T02:01:00Z',
              direction: 'outgoing'
            },
            {
              id: 46,
              preview: '[图片]',
              sender_name: 'Alice',
              occurred_at: '2026-11-04T02:02:00Z',
              direction: 'incoming',
              media: [
                {
                  id: 7,
                  kind: 'image',
                  media_url: '/v1/spaces/1/media/42'
                }
              ]
            }
          ],
          pagination: { page: 2, previous: 1 }
        }
      }
    })
    const wrapper = render({ kind: 'message', id: 44, conversation_id: 9 })
    await flushPromises()

    expect(spacesApi.getConversation).toHaveBeenCalledWith(1, 9)
    expect(spacesApi.getMessages).toHaveBeenCalledWith(1, 9, {
      page_size: 100,
      focus_message_id: 44
    })
    expect(wrapper.text()).toContain('客户群')
    expect(wrapper.find('.ev-msg.focus').text()).toContain('明天确认报价')
    expect(wrapper.text()).toContain('加载更早的消息')

    const image = wrapper.find('.ev-image')
    expect(image.exists()).toBe(true)
    expect(image.attributes('src')).toBe('blob:media')
    expect(wrapper.text()).not.toContain('[图片]')

    const detail = wrapper.find('.ev-btn')
    expect(detail.text()).toBe('在会话中打开')
    await detail.trigger('click')
    expect(wrapper.emitted('open-detail')[0][0]).toMatchObject({
      kind: 'message',
      id: 44,
      conversation_id: 9
    })
  })

  it('closes from the button and from Escape', async () => {
    spacesApi.getNote.mockResolvedValue({
      data: { data: { id: 3, title: '整理', content: '内容' } }
    })
    const wrapper = render({ kind: 'note', id: 3 })
    await flushPromises()

    await wrapper.find('.ev-close').trigger('click')
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toHaveLength(2)
  })
})
