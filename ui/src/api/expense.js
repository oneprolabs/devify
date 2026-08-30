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
  }
}

export default expenseApi
