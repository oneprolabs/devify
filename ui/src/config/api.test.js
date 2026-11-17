// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import apiConfig from './api'

describe('Google OAuth login URL', () => {
  it('returns the plain provider URL without a destination', () => {
    const url = apiConfig.endpoints.googleLogin()

    expect(
      url.startsWith(`${window.location.origin}/accounts/google/login/`)
    ).toBe(true)
    expect(new URL(url).search).toBe('')
  })

  it('routes the destination through the backend callback so tokens are issued', () => {
    const next = '/auth/desktop/authorize?client_id=desktop-client&state=abc'
    const url = apiConfig.endpoints.googleLogin(next)
    const outer = new URL(url)

    expect(outer.pathname).toBe('/accounts/google/login/')
    const callback = outer.searchParams.get('next')
    expect(callback.startsWith('/accounts/oauth/callback/?next=')).toBe(true)
    const inner = new URLSearchParams(callback.split('?')[1])
    expect(inner.get('next')).toBe(next)
  })
})
