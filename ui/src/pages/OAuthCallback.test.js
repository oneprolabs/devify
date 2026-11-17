// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import OAuthCallback from './OAuthCallback.vue'

const push = vi.fn()
const route = { query: {} }
const checkAuthStatus = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ push })
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key) => key }) }))
vi.mock('@/store/user', () => ({
  useUserStore: () => ({ checkAuthStatus })
}))
vi.mock('@/api/auth', () => ({ completeOAuthSetup: vi.fn() }))
vi.mock('@/components/ui/LanguageSwitcher.vue', () => ({
  default: { template: '<span />' }
}))
vi.mock('@/components/ui/UserSetupForm.vue', () => ({
  default: { template: '<form />' }
}))

const mountCallback = async (query) => {
  route.query = query
  const wrapper = mount(OAuthCallback, {
    global: { stubs: { RouterLink: true } }
  })
  await flushPromises()
  return wrapper
}

describe('OAuth callback destination', () => {
  beforeEach(() => {
    push.mockReset()
    checkAuthStatus.mockReset()
    checkAuthStatus.mockResolvedValue({
      profile: { registration_completed: true }
    })
  })

  it('returns to the desktop authorize link carried through the login', async () => {
    const wrapper = await mountCallback({
      access_token: 'access',
      refresh_token: 'refresh',
      next: '/auth/desktop/authorize?client_id=desktop-client&state=abc'
    })

    expect(push).toHaveBeenCalledWith(
      '/auth/desktop/authorize?client_id=desktop-client&state=abc'
    )
    wrapper.unmount()
  })

  it('falls back to the workspace when no next path is given', async () => {
    const wrapper = await mountCallback({
      access_token: 'access',
      refresh_token: 'refresh'
    })

    expect(push).toHaveBeenCalledWith('/workspace')
    wrapper.unmount()
  })

  it('ignores next paths that leave the site', async () => {
    const wrapper = await mountCallback({
      access_token: 'access',
      refresh_token: 'refresh',
      next: '//evil.example/steal'
    })

    expect(push).toHaveBeenCalledWith('/workspace')
    wrapper.unmount()
  })
})
