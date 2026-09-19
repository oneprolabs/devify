import { computed, ref } from 'vue'

/**
 * How large the interface type is.
 *
 * The canvas is drawn at a compact scale — 12px body, 11px meta — and that
 * is what ships. An earlier pass defaulted to the step above it, reasoning
 * that 12px is tight for sustained reading; the cost was that every page
 * stood 8% off its artboard, which made comparing the two useless and hid
 * real drift inside the gap. "large" stays a step for anyone who wants it.
 *
 * The chosen step lands on `<html data-font-size>`, which sets `--fs` in
 * tokens.css. Only type multiplies by it; widths, padding and row heights
 * stay where the canvas put them.
 */

const STORAGE_KEY = 'ui-font-size'
const SIZES = ['standard', 'large']
const DEFAULT_SIZE = 'standard'

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
