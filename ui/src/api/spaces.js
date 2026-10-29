import api from './index'

export const spacesApi = {
  getSpaces() {
    return api.get('/v1/spaces')
  },

  getSources(spaceId) {
    return api.get(`/v1/spaces/${spaceId}/sources`)
  }
}
