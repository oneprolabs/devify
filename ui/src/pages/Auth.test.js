// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import Auth from './Auth.vue'
import apiConfig from '@/config/api'

const route = { query: { forgot: '1' } }
vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ push: vi.fn() })
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key) => key, locale: { value: 'zh-CN' } })
}))
vi.mock('@/store/user', () => ({ useUserStore: () => ({}) }))
vi.mock('@/api/auth', () => ({
  sendRegistrationEmail: vi.fn(),
  resetPassword: vi.fn()
}))
vi.mock('@/config/api', () => ({
  default: { endpoints: { googleLogin: vi.fn(() => '') } }
}))
vi.mock('@/components/ui/BaseInput.vue', () => ({
  default: { template: '<input />' }
}))
vi.mock('@/components/ui/BaseButton.vue', () => ({
  default: { template: '<button><slot /></button>' }
}))
vi.mock('@/components/ui/LanguageSwitcher.vue', () => ({
  default: { template: '<span />' }
}))

describe('password recovery link', () => {
  it('opens the existing reset dialog directly from the login URL', () => {
    route.query = { forgot: '1' }
    const wrapper = mount(Auth)
    expect(wrapper.get('[role="dialog"]').text()).toContain(
      'auth.forgotPassword'
    )
    wrapper.unmount()
  })
})

describe('Google login redirect', () => {
  beforeEach(() => {
    apiConfig.endpoints.googleLogin.mockClear()
  })

  it('hands the desktop authorize link to the OAuth provider', () => {
    const next = '/auth/desktop/authorize?client_id=desktop-client&state=abc'
    route.query = { next }
    const wrapper = mount(Auth)
    expect(apiConfig.endpoints.googleLogin).toHaveBeenCalledWith(next)
    wrapper.unmount()
  })

  it('does not forward a destination outside the site', () => {
    route.query = { next: 'https://evil.example/steal' }
    const wrapper = mount(Auth)
    expect(apiConfig.endpoints.googleLogin).toHaveBeenCalledWith('')
    wrapper.unmount()
  })
})
