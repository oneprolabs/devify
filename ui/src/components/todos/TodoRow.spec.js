// @vitest-environment happy-dom
import { RouterLinkStub, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import TodoRow from './TodoRow.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key) => key, locale: ref('en-US') })
}))
vi.mock('@/store/preferences', () => ({
  usePreferencesStore: () => ({ currentTimezone: 'Asia/Shanghai' })
}))

describe('TodoRow source link', () => {
  it('uses the source email UUID for the chat route', () => {
    const wrapper = shallowMount(TodoRow, {
      props: {
        todo: {
          id: 1,
          content: 'Task',
          email_message: { id: 42, uuid: 'email-uuid', subject: 'Source' }
        }
      },
      global: { stubs: { RouterLink: RouterLinkStub } }
    })
    expect(wrapper.findComponent(RouterLinkStub).props('to')).toBe(
      '/chats/email-uuid'
    )
  })

  it('does not generate a broken link when the UUID is missing', () => {
    const wrapper = shallowMount(TodoRow, {
      props: {
        todo: {
          id: 1,
          content: 'Task',
          email_message: { id: 42, subject: 'Source' }
        }
      },
      global: { stubs: { RouterLink: RouterLinkStub } }
    })
    expect(wrapper.findComponent(RouterLinkStub).exists()).toBe(false)
  })

  it('does not show a source link for a manually created todo', () => {
    const wrapper = shallowMount(TodoRow, {
      props: { todo: { id: 2, content: 'Manual task', email_message: null } },
      global: { stubs: { RouterLink: RouterLinkStub } }
    })
    expect(wrapper.findComponent(RouterLinkStub).exists()).toBe(false)
  })
})
