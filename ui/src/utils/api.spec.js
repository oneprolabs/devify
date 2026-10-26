import { describe, expect, it } from 'vitest'

import { extractErrorMessage } from './api'

function apiError(data, message = 'Request failed with status code 400') {
  return { message, response: { data, status: 400 } }
}

describe('extractErrorMessage', () => {
  it('reads detail nested in the unified envelope', () => {
    const error = apiError({
      code: 400,
      message: 'failed',
      data: { detail: 'name is required' }
    })

    expect(extractErrorMessage(error)).toBe('name is required')
  })

  it('reads a plain DRF detail response', () => {
    expect(extractErrorMessage(apiError({ detail: 'Not found.' }))).toBe(
      'Not found.'
    )
  })

  it('reads DRF field errors', () => {
    const error = apiError({
      code: 400,
      message: 'failed',
      data: { email: ['Already exists.'] }
    })

    expect(extractErrorMessage(error)).toBe('Already exists.')
  })

  it('ignores the generic envelope message and falls back', () => {
    const error = apiError({ code: 500, message: 'failed', data: null })

    expect(extractErrorMessage(error, 'Save failed')).toBe(
      'Request failed with status code 400'
    )
  })

  it('falls back to the default message when nothing is available', () => {
    expect(extractErrorMessage({}, 'Save failed')).toBe('Save failed')
  })
})
