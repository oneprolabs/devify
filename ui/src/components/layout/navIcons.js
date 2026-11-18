import { h } from 'vue'

/**
 * Line icons for the app shell. Same 24px grid and 1.9 stroke as the design
 * canvas, so the sidebar and the mobile tab bar stay identical.
 */
const icon = (paths) => () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': '1.9'
    },
    paths()
  )

export const IconChats = icon(() => [
  h('path', {
    d: 'M21 12a8 8 0 01-11.3 7.3L4 21l1.7-5.7A8 8 0 1121 12z',
    'stroke-linejoin': 'round'
  })
])

export const IconApps = icon(() => [
  h('rect', { x: 3.5, y: 3.5, width: 7, height: 7, rx: 1.5 }),
  h('rect', { x: 13.5, y: 3.5, width: 7, height: 7, rx: 1.5 }),
  h('rect', { x: 3.5, y: 13.5, width: 7, height: 7, rx: 1.5 }),
  h('rect', { x: 13.5, y: 13.5, width: 7, height: 7, rx: 1.5 })
])

export const IconRelay = icon(() => [
  h('path', {
    d: 'M4 12h11M11 7l5 5-5 5M17 4h3v16h-3',
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round'
  })
])

export const IconTodos = icon(() => [
  h('rect', { x: 3.5, y: 3.5, width: 17, height: 17, rx: 4 }),
  h('path', {
    d: 'M8.5 12l2.5 2.5 4.5-5',
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round'
  })
])

export const IconExpense = icon(() => [
  h('path', {
    d: 'M6 3.5h12v17l-3-1.7-3 1.7-3-1.7-3 1.7v-17z',
    'stroke-linejoin': 'round'
  }),
  h('path', { d: 'M9 8h6M9 12h6', 'stroke-linecap': 'round' })
])

export const IconSettings = icon(() => [
  h('circle', { cx: 12, cy: 12, r: 3.2 }),
  h('path', {
    d: 'M12 2.5v2.8M12 18.7v2.8M21.5 12h-2.8M5.3 12H2.5M18.6 5.4l-2 2M7.4 16.6l-2 2M18.6 18.6l-2-2M7.4 7.4l-2-2',
    'stroke-linecap': 'round'
  })
])

export const IconBilling = icon(() => [
  h('rect', { x: 2.5, y: 5.5, width: 19, height: 13, rx: 2.5 }),
  h('path', { d: 'M2.5 10h19', 'stroke-linecap': 'round' })
])

export const IconOverview = icon(() => [
  h('rect', { x: 3.5, y: 3.5, width: 17, height: 17, rx: 3 }),
  h('path', { d: 'M3.5 9h17M9 9v11.5', 'stroke-linecap': 'round' })
])

export const IconConversations = icon(() => [
  h('path', { d: 'M5 7h14M5 12h14M5 17h9', 'stroke-linecap': 'round' })
])

export const IconEvents = icon(() => [
  h('path', {
    d: 'M6 20.5V4.5h11l-2.2 3.5L17 11.5H6',
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round'
  })
])

export const IconTopics = icon(() => [
  h('path', {
    d: 'M7 4.5h10v15l-5-2.6-5 2.6z',
    'stroke-linejoin': 'round'
  })
])

export const IconReports = icon(() => [
  h('path', { d: 'M7 3.5h7l3 3V20.5H7z', 'stroke-linejoin': 'round' }),
  h('path', {
    d: 'M14 3.5V7h3.5M9.5 11h5M9.5 14.5h5',
    'stroke-linecap': 'round'
  })
])

export const IconAsk = icon(() => [
  h('circle', { cx: 12, cy: 12, r: 8 }),
  h('path', {
    d: 'M9.6 9.4a2.4 2.4 0 114.2 1.6c-.7.7-1.3 1.1-1.3 2.2',
    'stroke-linecap': 'round'
  }),
  h('path', { d: 'M12 17.2h.01', 'stroke-linecap': 'round' })
])

export const IconSync = icon(() => [
  h('path', { d: 'M19 12a7 7 0 11-2-4.9', 'stroke-linecap': 'round' }),
  h('path', {
    d: 'M19 4.5V8h-3.5',
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round'
  })
])

export const IconDevice = icon(() => [
  h('rect', { x: 4, y: 5, width: 16, height: 11, rx: 1.5 }),
  h('path', { d: 'M9 19.5h6M12 16v3.5', 'stroke-linecap': 'round' })
])
