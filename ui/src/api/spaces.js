import api from './index'

export const spacesApi = {
  createSpace(data) {
    return api.post('/v1/spaces', data)
  },

  getInvitations() {
    return api.get('/v1/spaces/invitations')
  },

  getOwnerlessSpaces() {
    return api.get('/v1/admin/spaces/ownerless')
  },
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

  getUploads(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/chat/uploads`, { params })
  },

  createUpload(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/chat/uploads`, data)
  },

  uploadArchive(batchId, file) {
    const form = new FormData()
    form.append('archive', file)
    return api.put(`/v1/chat/uploads/${batchId}/archive`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  completeUpload(batchId) {
    return api.post(`/v1/chat/uploads/${batchId}/complete`)
  },

  getAnalysisJobs(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/analysis-jobs`, { params })
  },

  retryAnalysisJob(jobId) {
    return api.post(`/v1/analysis-jobs/${jobId}/retry`)
  },

  getMembers(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/members`)
  },

  inviteMember(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/members`, data)
  },

  updateMember(spaceId, userId, data) {
    return api.patch(`/v1/spaces/${spaceId}/members/${userId}`, data)
  },

  removeMember(spaceId, userId) {
    return api.delete(`/v1/spaces/${spaceId}/members/${userId}`)
  },

  acceptInvitation(spaceId, userId) {
    return api.post(`/v1/spaces/${spaceId}/members/${userId}/accept`)
  },

  rejectInvitation(spaceId, userId) {
    return api.delete(`/v1/spaces/${spaceId}/members/${userId}/accept`)
  },

  transferOwnership(spaceId, userId) {
    return api.post(`/v1/spaces/${spaceId}/ownership`, { user_id: userId })
  },

  updateSpace(spaceId, data) {
    return api.patch(`/v1/spaces/${spaceId}`, data)
  },

  takeoverSpace(spaceId, reason) {
    return api.post(`/v1/spaces/${spaceId}/takeover`, { reason })
  },

  endTakeover(spaceId) {
    return api.delete(`/v1/spaces/${spaceId}/takeover`)
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

  getEventRelations(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/event-relations`, { params })
  },

  createReport(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/reports`, data)
  }
}
