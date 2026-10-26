/**
 * API Response Utilities
 *
 * Handles the unified response format from backend:
 * {
 *   "code": 0,
 *   "message": "success",
 *   "data": { ... }
 * }
 */

/**
 * Extract data from unified API response format
 * @param {Object} response - Axios response object
 * @returns {any} - The actual data from response
 */
export function extractResponseData(response) {
  // Handle unified response format: { code, message, data }
  if (
    response.data &&
    typeof response.data === 'object' &&
    'data' in response.data
  ) {
    return response.data.data
  }

  // Fallback to direct response data
  return response.data
}

const GENERIC_ERROR_MESSAGES = new Set([
  'failed',
  'failure',
  'error',
  'success'
])

/**
 * Pick the most specific human-readable message out of a DRF / unified error
 * payload. Returns an empty string when nothing meaningful is present.
 */
function pickErrorMessage(body) {
  if (!body || typeof body !== 'object') {
    return ''
  }

  const detail = body.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }

  if (Array.isArray(body.non_field_errors) && body.non_field_errors.length) {
    return String(body.non_field_errors[0])
  }

  // Field-specific DRF errors, e.g. { email: ["Already exists."] }
  const firstFieldError = Object.values(body).find(
    (value) => Array.isArray(value) && value.length > 0
  )
  if (firstFieldError) {
    return String(firstFieldError[0])
  }

  const message = typeof body.message === 'string' ? body.message.trim() : ''
  if (message && !GENERIC_ERROR_MESSAGES.has(message.toLowerCase())) {
    return message
  }

  return ''
}

/**
 * Extract error message from API error response
 * @param {Object} error - Axios error object
 * @param {string} defaultMessage - Default error message
 * @returns {string} - Error message
 */
export function extractErrorMessage(
  error,
  defaultMessage = 'An error occurred'
) {
  const body = error?.response?.data

  if (typeof body === 'string' && body.trim()) {
    return body.trim()
  }

  if (body && typeof body === 'object') {
    // Unified envelope: { code, message, data: { detail: ... } }
    if (typeof body.data === 'string' && body.data.trim()) {
      return body.data.trim()
    }

    const nested = pickErrorMessage(body.data)
    if (nested) {
      return nested
    }

    const direct = pickErrorMessage(body)
    if (direct) {
      return direct
    }
  }

  return error?.message || defaultMessage
}

/**
 * Check if API response indicates success
 * @param {Object} response - Axios response object
 * @returns {boolean} - Whether the response indicates success
 */
export function isApiSuccess(response) {
  // HTTP status check
  if (response.status < 200 || response.status >= 300) {
    return false
  }

  // Unified response format check
  if (
    response.data &&
    typeof response.data === 'object' &&
    'code' in response.data
  ) {
    return response.data.code === 0
  }

  return true
}
