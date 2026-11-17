// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import UserFormModal from './UserFormModal.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key) => key })
}))

const groups = [{ id: 1, name: 'support' }]

const user = {
  id: 7,
  username: 'target-user',
  email: 'target@example.com',
  first_name: 'Target',
  last_name: 'User',
  is_staff: false,
  is_active: true,
  language: 'zh-CN',
  timezone: 'Asia/Shanghai',
  groups: []
}

const mountModal = (props = {}) =>
  mount(UserFormModal, {
    props: {
      show: true,
      mode: 'edit',
      user,
      groups,
      ...props
    }
  })

const clickButton = async (wrapper, label) => {
  const button = wrapper.findAll('button').find((item) => item.text() === label)
  expect(button).toBeTruthy()
  await button.trigger('click')
}

describe('UserFormModal', () => {
  it('prefills the edit form and emits permission changes', async () => {
    const wrapper = mountModal()

    const username = wrapper.get('input[type="text"]')
    expect(username.element.value).toBe('target-user')
    expect(username.element.disabled).toBe(true)

    await wrapper.get('#user-form-is-staff').setValue(true)
    await wrapper.get('#user-form-is-active').setValue(false)
    await wrapper.get('input[type="email"]').setValue('new@example.com')
    await clickButton(wrapper, 'management.saveChanges')

    const payload = wrapper.emitted('submit')[0][0]
    expect(payload).toMatchObject({
      username: 'target-user',
      email: 'new@example.com',
      first_name: 'Target',
      last_name: 'User',
      is_staff: true,
      is_active: false,
      group_ids: [],
      language: 'zh-CN',
      timezone: 'Asia/Shanghai'
    })
    expect(payload.password).toBe('')
    wrapper.unmount()
  })

  it('starts from an empty form in create mode', async () => {
    const wrapper = mountModal({ mode: 'create', user: null })

    const username = wrapper.get('input[type="text"]')
    expect(username.element.disabled).toBe(false)
    expect(username.element.value).toBe('')

    await username.setValue('new-user')
    await wrapper.get('input[type="password"]').setValue('secret12345')
    await wrapper.get('#user-form-is-staff').setValue(true)
    await clickButton(wrapper, 'common.confirm')

    const payload = wrapper.emitted('submit')[0][0]
    expect(payload).toMatchObject({
      username: 'new-user',
      password: 'secret12345',
      is_staff: true
    })
    wrapper.unmount()
  })
})
