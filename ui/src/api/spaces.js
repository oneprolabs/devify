import api from './index'

export const spacesApi = {
  getSpaces() {
    return api.get('/v1/spaces')
  },

  getSources(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/sources`)
  },

  getConversations(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/conversations`, { params })
  },

  getMessages(spaceId, conversationId, params = {}) {
    return api.get(
      `/v1/spaces/${spaceId}/conversations/${conversationId}/messages`,
      { params }
    )
  },

  getMessage(spaceId, conversationId, messageId) {
    return api.get(
      `/v1/spaces/${spaceId}/conversations/${conversationId}/messages/${messageId}`
    )
  }
}
