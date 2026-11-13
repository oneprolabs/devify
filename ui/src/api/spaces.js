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

  // Team email sources are API-only in the first release. Keep these
  // helpers for API clients, but do not wire them into a page.
  getEmailSources(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/email-sources`)
  },

  createEmailSource(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/email-sources`, data)
  },

  syncEmailSource(spaceId, mailboxUuid) {
    return api.post(`/v1/spaces/${spaceId}/email-sources/${mailboxUuid}/sync`)
  },

  testEmailSource(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/email-sources/test`, data)
  },

  testStoredEmailSource(spaceId, mailboxUuid) {
    return api.post(`/v1/spaces/${spaceId}/email-sources/${mailboxUuid}/test`)
  },

  updateEmailSource(spaceId, mailboxUuid, data) {
    return api.patch(`/v1/spaces/${spaceId}/email-sources/${mailboxUuid}`, data)
  },

  disableEmailSource(spaceId, mailboxUuid) {
    return api.delete(`/v1/spaces/${spaceId}/email-sources/${mailboxUuid}`)
  },

  getSources(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/sources`)
  },

  verifySource(sourceId) {
    return api.post(`/v1/sources/${sourceId}/verify`)
  },

  getSourceStatus(sourceId) {
    return api.get(`/v1/sources/${sourceId}/status`)
  },

  getSourceJobs(sourceId) {
    return api.get(`/v1/sources/${sourceId}/jobs`)
  },

  getConversations(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/conversations`, { params })
  },

  getConversation(spaceId, conversationId) {
    return api.get(`/v1/spaces/${spaceId}/conversations/${conversationId}`)
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

  getEventTags(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/tags`)
  },

  createEventTag(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/tags`, data)
  },

  updateEventTag(tagId, data) {
    return api.patch(`/v1/tags/${tagId}`, data)
  },

  deleteEventTag(tagId) {
    return api.delete(`/v1/tags/${tagId}`)
  },

  addEventTag(eventId, tagId) {
    return api.post(`/v1/events/${eventId}/tags`, { tag_id: tagId })
  },

  removeEventTag(eventId, tagId) {
    return api.delete(`/v1/events/${eventId}/tags/${tagId}`)
  },

  getEvent(eventId) {
    return api.get(`/v1/events/${eventId}`)
  },

  getEventNotes(eventId, params = {}) {
    return api.get(`/v1/events/${eventId}/notes`, { params })
  },

  assignEventNotes(eventId, noteIds) {
    return api.post(`/v1/events/${eventId}/notes`, { note_ids: noteIds })
  },

  removeEventNote(eventId, noteId) {
    return api.delete(`/v1/events/${eventId}/notes/${noteId}`)
  },

  getReports(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/reports`, { params })
  },

  getTopics(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/topics`)
  },

  createTopic(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/topics`, data)
  },

  updateTopic(topicId, data) {
    return api.patch(`/v1/topics/${topicId}`, data)
  },

  deleteTopic(topicId) {
    return api.delete(`/v1/topics/${topicId}`)
  },

  getTopicReports(topicId) {
    return api.get(`/v1/topics/${topicId}/reports`)
  },

  runTopic(topicId) {
    return api.post(`/v1/topics/${topicId}/run`)
  },

  getQuestions(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/questions`)
  },

  copySpaceResources(targetSpaceId, data) {
    return api.post(`/v1/spaces/${targetSpaceId}/resource-copies`, data)
  },

  getQuestion(spaceId, questionId) {
    return api.get(`/v1/spaces/${spaceId}/questions/${questionId}`)
  },

  askQuestion(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/questions`, data)
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

  retryUpload(batchId) {
    return api.post(`/v1/chat/uploads/${batchId}/retry`)
  },

  getUploadItem(batchId, itemId) {
    return api.get(`/v1/chat/uploads/${batchId}/items/${itemId}`)
  },

  getAnalysisJobs(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/analysis-jobs`, { params })
  },

  retryAnalysisJob(jobId) {
    return api.post(`/v1/analysis-jobs/${jobId}/retry`)
  },

  cancelAnalysisJob(jobId) {
    return api.post(`/v1/analysis-jobs/${jobId}/cancel`)
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

  getQuotaUsage(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/quota/usage`)
  },

  getQuota(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/quota`)
  },

  updateQuota(spaceId, data) {
    return api.patch(`/v1/spaces/${spaceId}/quota`, data)
  },

  getAuditLogs(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/audit-logs`, { params })
  },

  getWorkflowConfig(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/workflow-config`)
  },

  updateWorkflowConfig(spaceId, data) {
    return api.patch(`/v1/spaces/${spaceId}/workflow-config`, data)
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

  getEventRelation(relationId) {
    return api.get(`/v1/event-relations/${relationId}`)
  },

  updateEventRelation(relationId, data) {
    return api.patch(`/v1/event-relations/${relationId}`, data)
  },

  deleteEventRelation(relationId) {
    return api.delete(`/v1/event-relations/${relationId}`)
  },

  getEventSuggestions(spaceId, params = {}) {
    return api.get(`/v1/spaces/${spaceId}/event-suggestions`, { params })
  },

  reviewEventSuggestion(suggestionId, decision) {
    return api.post(`/v1/event-suggestions/${suggestionId}/review`, {
      decision
    })
  },

  createReport(spaceId, data) {
    return api.post(`/v1/spaces/${spaceId}/reports`, data)
  }
}
