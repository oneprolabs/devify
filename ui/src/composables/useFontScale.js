import { computed, ref } from 'vue'

/**
 * How large the interface type is.
 *
 * The canvas is drawn at a compact scale — 12px body, 11px meta — which is
 * tight for sustained reading, so the app ships one step larger and keeps
 * the canvas size available as "standard" for anyone comparing against it.
 *
 * The chosen step lands on `<html data-font-size>`, which sets `--fs` in
 * tokens.css. Only type multiplies by it; widths, padding and row heights
 * stay where the canvas put them.
 */

const STORAGE_KEY = 'ui-font-size'
const SIZES = ['standard', 'large']
const DEFAULT_SIZE = 'large'

const readStored = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return SIZES.includes(stored) ? stored : DEFAULT_SIZE
  } catch {
    return DEFAULT_SIZE
  }
}

const size = ref(readStored())

const apply = () => {
  document.documentElement.dataset.fontSize = size.value
}

const setSize = (next) => {
  if (!SIZES.includes(next)) return
  size.value = next
  apply()
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    // A blocked storage API is not a reason to refuse the change.
  }
}

/** Set the stored size before the app mounts, so there is no reflow. */
export function initFontScale() {
  apply()
}

export function useFontScale() {
  return { size: computed(() => size.value), setSize, sizes: SIZES }
}
