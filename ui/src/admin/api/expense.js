/**
 * Expense admin API.
 */
import apiClient from '@/api/index'

function extractData(res) {
  const body = res?.data
  if (body && typeof body === 'object' && 'data' in body) return body.data
  return body ?? res
}

export const expenseAdminApi = {
  getExpenseConfig() {
    return apiClient.get('/v1/admin/apps/expense/config').then(extractData)
  },

  updateExpenseConfig(body) {
    return apiClient
      .put('/v1/admin/apps/expense/config', body)
      .then(extractData)
  }
}
