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
  },

  getLinks(params = {}) {
    return apiClient.get('/v1/apps/expense/links', { params }).then(extractData)
  },

  releaseLink(uuid) {
    return apiClient
      .post(`/v1/apps/expense/links/${uuid}/allow`)
      .then(extractData)
  },

  getInvoices(params = {}) {
    return apiClient
      .get('/v1/apps/expense/invoices', { params })
      .then(extractData)
  },

  getInvoice(uuid) {
    return apiClient.get(`/v1/apps/expense/invoices/${uuid}`).then(extractData)
  },

  updateInvoice(uuid, payload) {
    return apiClient
      .patch(`/v1/apps/expense/invoices/${uuid}`, payload)
      .then(extractData)
  },

  reextractInvoice(uuid) {
    return apiClient
      .post(`/v1/apps/expense/invoices/${uuid}/reextract`)
      .then(extractData)
  },

  getGroups() {
    return apiClient.get('/v1/apps/expense/groups').then(extractData)
  },

  createGroup(payload) {
    return apiClient.post('/v1/apps/expense/groups', payload).then(extractData)
  },

  getGroupSummary(uuid) {
    return apiClient
      .get(`/v1/apps/expense/groups/${uuid}/summary`)
      .then(extractData)
  },

  getGroup(uuid) {
    return apiClient.get(`/v1/apps/expense/groups/${uuid}`).then(extractData)
  },

  addGroupItems(uuid, invoiceUuids) {
    return apiClient
      .post(`/v1/apps/expense/groups/${uuid}/items`, {
        invoice_uuids: invoiceUuids
      })
      .then(extractData)
  },

  removeGroupItems(uuid, invoiceUuids) {
    return apiClient
      .delete(`/v1/apps/expense/groups/${uuid}/items`, {
        data: { invoice_uuids: invoiceUuids }
      })
      .then(extractData)
  },

  getTrips() {
    return apiClient.get('/v1/apps/expense/trips').then(extractData)
  },

  refreshTrips() {
    return apiClient.post('/v1/apps/expense/trips').then(extractData)
  },

  acceptTrip(uuid) {
    return apiClient
      .post(`/v1/apps/expense/trips/${uuid}/accept`)
      .then(extractData)
  },

  dismissTrip(uuid) {
    return apiClient
      .post(`/v1/apps/expense/trips/${uuid}/dismiss`)
      .then(extractData)
  }
}

export default expenseApi
