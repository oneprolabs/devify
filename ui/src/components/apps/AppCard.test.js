// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { markRaw } from 'vue'
import AppCard from './AppCard.vue'
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: key => key }) }))
describe('AppCard', () => {
  it('allows opening an application without statistics on desktop', async () => {
    const wrapper = mount(AppCard, { props: { name: 'Application', icon: markRaw({ template: '<span />' }) } })
    const button = wrapper.find('button.md\\:flex')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    expect(wrapper.emitted('open')).toHaveLength(1)
  })
})
