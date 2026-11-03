// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ReportWorkspace from './ReportWorkspace.vue'

const reports = [
  {
    id: 1,
    title: '客户交付日报 · 11/01',
    status: 'ready',
    period_start: '2026-11-01T00:00:00Z',
    period_end: '2026-11-01T23:59:00Z'
  },
  {
    id: 2,
    title: 'LATAM 项目周报',
    status: 'failed',
    period_start: '2026-10-26T00:00:00Z',
    period_end: '2026-11-01T23:59:00Z'
  },
  {
    id: 3,
    title: '10 月工作月报',
    status: 'queued'
  }
]
const selected = {
  ...reports[0],
  body: '本周交付正常。',
  sections: [
    {
      id: 1,
      title: '交付进展',
      items: [
        {
          id: 9,
          title: '英文版周五前交付',
          summary: '客户确认周五前给出英文版。',
          sources: [{ id: 5, source_kind: 'event', event_id: 12 }]
        }
      ]
    }
  ]
}
const render = (props = {}) =>
  mount(ReportWorkspace, {
    props: { spaceId: 3, reports, selected, ...props }
  })

describe('ReportWorkspace', () => {
  it('filters reports by status and emits selection', async () => {
    const wrapper = render()
    expect(wrapper.findAll('.ws-row')).toHaveLength(3)
    expect(wrapper.find('.ws-rail').text()).toContain('3 份')
    await wrapper.findAll('.ws-seg button')[3].trigger('click')
    expect(wrapper.findAll('.ws-row')).toHaveLength(1)
    expect(wrapper.find('.ws-row').text()).toContain('LATAM')
    await wrapper.find('.ws-row').trigger('click')
    expect(wrapper.emitted('select')[0][0].id).toBe(2)
  })

  it('renders report sections and opens their evidence', async () => {
    const wrapper = render()
    expect(wrapper.find('.ws-display').text()).toContain('客户交付日报')
    expect(wrapper.text()).toContain('本周交付正常。')
    expect(wrapper.text()).toContain('1 个分组 · 1 条记录')
    expect(wrapper.text()).toContain('英文版周五前交付')
    await wrapper.find('.ws-li-action').trigger('click')
    expect(wrapper.emitted('open-citation')[0][0]).toMatchObject({
      kind: 'event',
      id: 12
    })
  })

  it('explains when a report has no sections', () => {
    const wrapper = render({ selected: { ...reports[0], sections: [] } })
    expect(wrapper.text()).toContain('只有正文')
  })

  it('offers creation only when permitted', async () => {
    const wrapper = render({ canCreate: true })
    const buttons = wrapper.findAll('.ws-det-actions button')
    expect(buttons.some((button) => button.text().includes('新建报告'))).toBe(
      true
    )
    await buttons
      .find((button) => button.text().includes('新建报告'))
      .trigger('click')
    expect(wrapper.emitted('create')).toBeTruthy()
  })
})
