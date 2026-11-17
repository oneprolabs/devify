// API configuration for the application
// Centralizes all API endpoints and base URLs

// Get base URL from environment variables
// Format: http://localhost:8000 or https://api.example.com
const getBaseUrl = () => {
  // Check if VITE_API_BASE_URL is set
  const envUrl = import.meta.env.VITE_API_BASE_URL

  if (envUrl) {
    // If VITE_API_BASE_URL includes /api, strip it
    return envUrl.endsWith('/api') ? envUrl.replace('/api', '') : envUrl
  }

  // Default for development in Docker
  return window.location.origin
}

// Get API base URL (for API endpoints)
const getApiBaseUrl = () => {
  const baseUrl = getBaseUrl()
  return `${baseUrl}/api`
}

// Get OAuth base URL (for OAuth endpoints like Google login)
// For production, use the same base URL as API
// For development without env variable, use window.location.origin
const getOAuthBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  if (envUrl) {
    return envUrl.endsWith('/api') ? envUrl.replace('/api', '') : envUrl
  }
  // Use current origin as fallback (works for both dev and production)
  return window.location.origin
}

// Export configuration
export default {
  baseUrl: getBaseUrl(),
  apiBaseUrl: getApiBaseUrl(),
  oauthBaseUrl: getOAuthBaseUrl(),

  // OAuth endpoints
  endpoints: {
    // `next` is the in-app path to return to after the provider round trip
    // (e.g. the desktop client's /auth/desktop/authorize?... link). The
    // backend callback turns it into JWT tokens before handing the path back.
    googleLogin: (next) => {
      const loginUrl = `${getOAuthBaseUrl()}/accounts/google/login/`
      if (!next) return loginUrl
      const callbackUrl = `/accounts/oauth/callback/?${new URLSearchParams({
        next
      })}`
      return `${loginUrl}?${new URLSearchParams({ next: callbackUrl })}`
    },
    wechatLogin: () => `${getOAuthBaseUrl()}/accounts/weixin/login/`,
    oauthCallback: () => `${getOAuthBaseUrl()}/accounts/oauth/callback/`
  }
}
