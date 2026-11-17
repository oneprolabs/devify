// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { loginRedirectUrl } from './index'

describe('login redirect', () => {
  it('remembers the page that needed a signed-in user', () => {
    const url = loginRedirectUrl({
      pathname: '/auth/desktop/authorize',
      search: '?state=abc&redirect_uri=http%3A%2F%2F127.0.0.1%3A47832'
    })

    expect(url).toBe(
      '/login?next=%2Fauth%2Fdesktop%2Fauthorize%3Fstate%3Dabc%26redirect_uri%3Dhttp%253A%252F%252F127.0.0.1%253A47832'
    )
  })

  it('stays put on the login page instead of looping', () => {
    expect(loginRedirectUrl({ pathname: '/login', search: '' })).toBe('')
  })

  it('does not echo credential-bearing auth pages into the login URL', () => {
    expect(
      loginRedirectUrl({
        pathname: '/auth/oauth/callback',
        search: '?access_token=leaked'
      })
    ).toBe('')
  })
})
