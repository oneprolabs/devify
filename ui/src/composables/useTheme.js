import { computed, ref, watch } from 'vue'

/**
 * Theme state for the whole app.
 *
 * `mode` is what the user picked (light / dark / system); `resolved` is what
 * is actually painted. The resolved value lands on `<html data-theme>`, which
 * is where `tokens.css` switches palettes.
 */

const STORAGE_KEY = 'ui-theme'
const MODES = ['light', 'dark', 'system']

const readStoredMode = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return MODES.includes(stored) ? stored : 'system'
  } catch {
    return 'system'
  }
}

const mode = ref(readStoredMode())
const systemPrefersDark = ref(false)

const media =
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null

if (media) {
  systemPrefersDark.value = media.matches
  media.addEventListener('change', (event) => {
    systemPrefersDark.value = event.matches
  })
}

const resolvedTheme = computed(() => {
  if (mode.value === 'system') {
    return systemPrefersDark.value ? 'dark' : 'light'
  }
  return mode.value
})

const applyTheme = () => {
  document.documentElement.dataset.theme = resolvedTheme.value
}

watch(resolvedTheme, applyTheme)

const setMode = (next) => {
  if (!MODES.includes(next)) return
  mode.value = next
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    // A blocked storage API is not a reason to refuse the theme change.
  }
}

/** Paint the stored theme before the app mounts, so there is no flash. */
export function initTheme() {
  applyTheme()
}

export function useTheme() {
  return { mode, resolvedTheme, setMode, modes: MODES }
}
