import { reactive } from 'vue'

const toastState = reactive({
  show: false,
  message: '',
  type: 'info',
  duration: 4000
})

let hideTimer = null
let showTimer = null

const clearTimer = () => {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

const clearShowTimer = () => {
  if (showTimer) {
    clearTimeout(showTimer)
    showTimer = null
  }
}

const showToast = (message, type, duration) => {
  clearTimer()
  clearShowTimer()

  if (toastState.show) {
    toastState.show = false
    showTimer = setTimeout(() => {
      toastState.message = message
      toastState.type = type
      toastState.duration = duration
      toastState.show = true
      startAutoHide(duration)
      showTimer = null
    }, 150)
  } else {
    toastState.message = message
    toastState.type = type
    toastState.duration = duration
    toastState.show = true
    startAutoHide(duration)
  }
}

const startAutoHide = (duration) => {
  clearTimer()
  // A failure stays until it is dismissed. Everything else says something
  // went right and can leave on its own.
  if (!duration) return
  hideTimer = setTimeout(() => {
    hide()
  }, duration)
}

const hide = () => {
  clearTimer()
  toastState.show = false
}

export function useToast() {
  return {
    showSuccess: (message, duration = 4000) => {
      showToast(message, 'success', duration)
    },
    showError: (message, duration = 0) => {
      showToast(message, 'error', duration)
    },
    showWarning: (message, duration = 4000) => {
      showToast(message, 'warning', duration)
    },
    showInfo: (message, duration = 3000) => {
      showToast(message, 'info', duration)
    },
    hide,
    state: toastState
  }
}
