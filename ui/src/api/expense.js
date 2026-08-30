import apiClient from './index'

function extractData(response) {
  const payload = response?.data
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data
  }
  return payload ?? response
}

export const expenseApi = {
  getConfig() {
    return apiClient.get('/v1/apps/expense/config').then(extractData)
  },

  updateConfig(payload) {
    return apiClient.patch('/v1/apps/expense/config', payload).then(extractData)
  },

  previewScan(payload = {}) {
    return apiClient
      .post('/v1/apps/expense/scan/preview', payload)
      .then(extractData)
  },

  startScan(payload = {}) {
    return apiClient.post('/v1/apps/expense/scan', payload).then(extractData)
  },

  getScanRuns() {
    return apiClient.get('/v1/apps/expense/scan-runs').then(extractData)
  },

  getScanRun(uuid) {
    return apiClient.get(`/v1/apps/expense/scan-runs/${uuid}`).then(extractData)
  }
}

export default expenseApi
