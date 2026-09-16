// @vitest-environment happy-dom

import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import UserSetupForm from './UserSetupForm.vue'

vi.mock('vue-i18n', async () => {
  const { ref } = await vi.importActual('vue')
  return {
    useI18n: () => ({
      t: (key) => key,
      locale: ref('en')
    })
  }
})

const stubs = {
  VirtualEmailInput: {
    props: ['error'],
    template: '<div data-test="virtual-email">{{ error }}</div>'
  },
  BaseInput: {
    props: ['error', 'name'],
    template: '<div :data-test="`input-${name}`">{{ error }}</div>'
  },
  SceneSelector: true,
  BaseButton: true
}

const mountForm = (props = {}) =>
  mount(UserSetupForm, { props, global: { stubs } })

describe('UserSetupForm.setError', () => {
  it('maps snake_case API field errors onto camelCase form fields', async () => {
    const wrapper = mountForm({ requirePassword: true })

    wrapper.vm.setError('virtual_email_username', 'Username taken')
    await nextTick()

    expect(wrapper.get('[data-test="virtual-email"]').text()).toBe(
      'Username taken'
    )
  })

  it('maps confirm_password onto the confirm password field', async () => {
    const wrapper = mountForm({ requirePassword: true })

    wrapper.vm.setError('confirm_password', 'Passwords do not match')
    await nextTick()

    expect(wrapper.get('[data-test="input-confirmPassword"]').text()).toBe(
      'Passwords do not match'
    )
  })

  it('takes the first message when the API returns an array', async () => {
    const wrapper = mountForm()

    wrapper.vm.setError('virtualEmailUsername', ['First', 'Second'])
    await nextTick()

    expect(wrapper.get('[data-test="virtual-email"]').text()).toBe('First')
  })

  it('ignores unknown fields without throwing', () => {
    const wrapper = mountForm()

    expect(() => wrapper.vm.setError('unknown_field', 'boom')).not.toThrow()
  })
})
