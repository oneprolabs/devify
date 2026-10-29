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
  },

  getNotes(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/notes`, { params })
  },

  getNote(noteId) {
    return api.get(`/v1/notes/${noteId}`)
  },

  getEvents(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/events`, { params })
  },

  getEvent(eventId) {
    return api.get(`/v1/events/${eventId}`)
  },

  getReports(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/reports`, { params })
  },

  getReport(reportId) {
    return api.get(`/v1/reports/${reportId}`)
  }
}
