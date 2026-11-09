import { reactive } from 'vue'
import api from '@/api'

/**
 * Avatar pictures are private to the space, so they cannot be used as plain
 * `<img src>`: the browser would not send the bearer token. They are fetched
 * as blobs with the normal API client and cached by their absolute URL, which
 * already carries the content digest.
 */
const blobs = reactive({})

const load = (url) => {
  blobs[url] = ''
  api
    .get(url, { responseType: 'blob' })
    .then((response) => {
      blobs[url] = URL.createObjectURL(response.data)
    })
    .catch(() => {
      blobs[url] = ''
    })
}

export function useAvatars() {
  const resolve = (url) => {
    if (!url) return ''
    if (!(url in blobs)) load(url)
    return blobs[url]
  }
  return { resolve }
}
