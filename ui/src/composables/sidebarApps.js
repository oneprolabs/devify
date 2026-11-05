import { ref } from 'vue'
import { relayApi } from '@/api/relay'

/**
 * Apps enabled for each space, cached for the whole session.
 *
 * Every page mounts its own layout, so the sidebar is recreated on each
 * navigation. Keeping the result here means the 应用中心 tree renders its
 * previous items immediately instead of collapsing to an empty list while the
 * request runs again.
 */
const appsBySpace = ref({})
const requests = new Map()

export function useScopedApps() {
  return appsBySpace
}

/** Test helper: clear the session cache so a suite starts from a clean slate. */
export function resetScopedAppsCache() {
  appsBySpace.value = {}
  requests.clear()
}

export function loadScopedApps(spaceId) {
  if (spaceId === undefined || spaceId === null || spaceId === '') {
    return Promise.resolve([])
  }
  const key = String(spaceId)
  if (Object.prototype.hasOwnProperty.call(appsBySpace.value, key)) {
    return Promise.resolve(appsBySpace.value[key])
  }
  if (!requests.has(key)) {
    const request = relayApi
      .getApps(spaceId)
      .then((apps) => {
        const list = Array.isArray(apps) ? apps : []
        appsBySpace.value = { ...appsBySpace.value, [key]: list }
        return list
      })
      .catch(() => {
        // Fail closed. Caching the empty list keeps a flaky request from
        // making the tree flash on every navigation.
        appsBySpace.value = { ...appsBySpace.value, [key]: [] }
        return []
      })
      .finally(() => {
        requests.delete(key)
      })
    requests.set(key, request)
  }
  return requests.get(key)
}
