// @vitest-environment happy-dom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import FilterSelect from './FilterSelect.vue'

describe('FilterSelect', () => {
  let wrapper

  afterEach(() => {
    wrapper?.unmount()
    document.body
      .querySelectorAll('[data-filter-select-menu]')
      .forEach((menu) => menu.remove())
  })

  it('teleports the open menu outside clipping ancestors and selects an option', async () => {
    wrapper = mount(FilterSelect, {
      attachTo: document.body,
      props: {
        label: '状态：全部',
        options: [
          { value: null, label: '全部' },
          { value: false, label: '未完成' },
          { value: true, label: '已完成' }
        ],
        modelValue: null,
        size: 'sm'
      }
    })

    await wrapper.get('button').trigger('click')

    const menu = document.body.querySelector('[data-filter-select-menu]')
    expect(menu).not.toBeNull()
    expect(menu.parentElement).toBe(document.body)
    expect(menu.querySelectorAll('button')).toHaveLength(3)

    menu.querySelectorAll('button')[1].click()
    await flushPromises()

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    expect(document.body.querySelector('[data-filter-select-menu]')).toBeNull()
  })
})
