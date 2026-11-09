import { reactive } from 'vue'
import api from '@/api'

const blobs = reactive({})
const pending = new Map()

/** Resolve a private chat attachment to an authenticated blob URL. */
export function useChatMedia() {
  const resolve = (url) => {
    if (!url) return ''
    if (!(url in blobs) && !pending.has(url)) {
      blobs[url] = ''
      const request = api
        .get(url, { responseType: 'blob' })
        .then((response) => {
          blobs[url] = URL.createObjectURL(response.data)
        })
        .catch(() => {
          blobs[url] = ''
        })
        .finally(() => pending.delete(url))
      pending.set(url, request)
    }
    return blobs[url]
  }
  return { resolve }
}
