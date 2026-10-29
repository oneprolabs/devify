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
  },

  createNote(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/notes`, data)
  },

  updateNote(noteId, data) {
    return api.patch(`/v1/notes/${noteId}`, data)
  },

  addNoteEvidence(noteId, data) {
    return api.post(`/v1/notes/${noteId}/evidence`, data)
  },

  createEvent(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/events`, data)
  },

  updateEvent(eventId, data) {
    return api.patch(`/v1/events/${eventId}`, data)
  },

  createEventRelation(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/event-relations`, data)
  },

  createReport(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/reports`, data)
  }
}
