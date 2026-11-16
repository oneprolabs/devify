// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Auth from './Auth.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { forgot: '1' } }),
  useRouter: () => ({ push: vi.fn() })
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key) => key, locale: { value: 'zh-CN' } }) }))
vi.mock('@/store/user', () => ({ useUserStore: () => ({}) }))
vi.mock('@/api/auth', () => ({ sendRegistrationEmail: vi.fn(), resetPassword: vi.fn() }))
vi.mock('@/config/api', () => ({ default: { endpoints: { googleLogin: () => '' } } }))
vi.mock('@/components/ui/BaseInput.vue', () => ({ default: { template: '<input />' } }))
vi.mock('@/components/ui/BaseButton.vue', () => ({ default: { template: '<button><slot /></button>' } }))
vi.mock('@/components/ui/LanguageSwitcher.vue', () => ({ default: { template: '<span />' } }))

describe('password recovery link', () => {
  it('opens the existing reset dialog directly from the login URL', () => {
    const wrapper = mount(Auth)
    expect(wrapper.get('[role="dialog"]').text()).toContain('auth.forgotPassword')
    wrapper.unmount()
  })
})
