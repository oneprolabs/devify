// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NoteWorkspace from './NoteWorkspace.vue'

const note = {
  id: 7,
  title: '整理记录',
  content: '第一段内容。'.repeat(120),
  origin: 'auto',
  assignment_mode: 'auto',
  created_at: '2026-10-29T11:19:00Z',
  evidence: [
    {
      id: 1,
      message_id: 1201,
      conversation_id: 2,
      sender_name: '都乐',
      reference_key: '1201:whole'
    }
  ],
  event_ids: [13]
}
const render = (props = {}) =>
  mount(NoteWorkspace, {
    props: {
      spaceId: 3,
      notes: [note],
      selected: note,
      canEdit: true,
      ...props
    }
  })

describe('NoteWorkspace', () => {
  it('renders the note once and expands long content', async () => {
    const wrapper = render()
    expect(wrapper.find('.ws-rail').text()).toContain('整理记录')
    expect(wrapper.find('.note-content').text().endsWith('…')).toBe(true)
    expect(wrapper.find('.note-toggle').text()).toBe('展开全文')
    await wrapper.find('.note-toggle').trigger('click')
    expect(wrapper.find('.note-content').text().endsWith('…')).toBe(false)
    expect(wrapper.find('.note-toggle').text()).toBe('收起全文')
  })

  it('opens message evidence and linked events', async () => {
    const wrapper = render()
    await wrapper.find('.ws-li-action').trigger('click')
    expect(wrapper.emitted('open-message')[0][0]).toMatchObject({
      kind: 'message',
      id: 1201,
      conversation_id: 2
    })
    const eventRow = wrapper
      .findAll('.ws-li')
      .find((row) => row.text().includes('事件 #13'))
    await eventRow.trigger('click')
    expect(wrapper.emitted('open-event')[0][0]).toBe(13)
  })

  it('submits a new evidence message id', async () => {
    const wrapper = render()
    await wrapper.find('.evidence-form input').setValue('1202')
    await wrapper.find('.evidence-form').trigger('submit')
    expect(wrapper.emitted('add-evidence')[0][0]).toBe(1202)
  })
})
