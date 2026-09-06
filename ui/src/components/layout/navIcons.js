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
