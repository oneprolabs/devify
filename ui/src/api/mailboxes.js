import apiClient from './index'

function extractData(response) {
  const payload = response?.data
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data
  }
  return payload ?? response
}

export const mailboxApi = {
  list() {
    return apiClient.get('/v1/settings/mailboxes').then(extractData)
  },

  create(payload) {
    return apiClient.post('/v1/settings/mailboxes', payload).then(extractData)
  },

  update(uuid, payload) {
    return apiClient
      .patch(`/v1/settings/mailboxes/${uuid}`, payload)
      .then(extractData)
  },

  remove(uuid) {
    return apiClient.delete(`/v1/settings/mailboxes/${uuid}`).then(extractData)
  },

  testDraft(payload) {
    return apiClient
      .post('/v1/settings/mailboxes/test', payload)
      .then(extractData)
  },

  testStored(uuid) {
    return apiClient
      .post(`/v1/settings/mailboxes/${uuid}/test`)
      .then(extractData)
  }
}

export default mailboxApi
