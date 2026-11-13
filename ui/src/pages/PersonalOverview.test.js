// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PersonalOverview from './PersonalOverview.vue'
import { spacesApi } from '@/api/spaces'
import { authApi } from '@/api/auth'

vi.mock('@/api/auth', () => ({ authApi: { getDesktopDevices: vi.fn() } }))

vi.mock('@/components/layout/AppLayout.vue', () => ({
  default: { template: '<div><slot /></div>' }
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('@/api/spaces', () => ({
  spacesApi: {
    getSpaces: vi.fn(),
    getEvents: vi.fn(),
    getReports: vi.fn(),
    getUploads: vi.fn(),
    getConversations: vi.fn(),
    getTopics: vi.fn(),
    takeoverSpace: vi.fn()
  }
}))

const push = vi.fn()
const spaceId = 3
const paginated = (list) => ({
  data: {
    data: {
      list,
      pagination: {
        total: list.length,
        page: 1,
        page_size: 100,
        next: null,
        previous: null
      }
    }
  }
})
const events = [
  { id: 1, title: '待处理事件一', status: 'open', tags: [{ label: '客户' }] },
  { id: 2, title: '已完成事件', status: 'done', tags: [] },
  { id: 3, title: '待处理事件二', status: 'in_progress', tags: [] },
  { id: 4, title: '待处理事件三', status: 'open', tags: [] },
  { id: 5, title: '待处理事件四', status: 'open', tags: [] },
  { id: 6, title: '待处理事件五', status: 'open', tags: [] },
  { id: 7, title: '待处理事件六', status: 'open', tags: [] }
].map((event, index) => ({
  ...event,
  last_activity_at: new Date(
    Date.UTC(2026, 10, 10) - index * 1000
  ).toISOString()
}))
const uploads = [101, 102, 103, 104, 105].map((id, index) => ({
  id,
  status: index === 1 ? 'processing' : 'completed',
  created_at: `2026-11-0${5 - index}T08:00:00Z`,
  message_count: 20 + index,
  source_type: 'wechat'
}))
const reports = [
  {
    id: 91,
    title: '最新客户报告',
    body: '这是来自接口的报告正文。',
    created_at: '2026-11-05T08:00:00Z'
  },
  {
    id: 90,
    title: '较早的报告',
    body: '旧正文',
    created_at: '2026-11-01T08:00:00Z'
  }
]
const conversations = [
  { id: 11, message_count: 900 },
  { id: 12, message_count: 350 },
  { id: 13, message_count: 3 }
]
const topics = [
  { id: 21, enabled: true },
  { id: 22, enabled: false }
]
const space = {
  id: spaceId,
  is_global_admin: false,
  admin_takeover_active: false
}

function button(wrapper, label) {
  const matches = wrapper
    .findAll('button')
    .filter((item) => item.text().includes(label))
  expect(matches, `button containing ${label}`).toHaveLength(1)
  return matches[0]
}

function expectMetric(wrapper, label, value) {
  expect(button(wrapper, label).text()).toMatch(
    new RegExp(`${label}\\s*${value}`)
  )
}

function mountPage() {
  return mount(PersonalOverview, { props: { spaceId } })
}

describe('PersonalOverview', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    localStorage.clear()
    authApi.getDesktopDevices.mockResolvedValue({
      data: { data: [{ device_id: 'device-1', status: 'active' }] }
    })
    spacesApi.getSpaces.mockResolvedValue({ data: { data: [space] } })
    spacesApi.getEvents.mockImplementation((id, { status }) =>
      Promise.resolve(
        paginated(events.filter((event) => event.status === status))
      )
    )
    spacesApi.getReports.mockResolvedValue(paginated(reports))
    spacesApi.getUploads.mockResolvedValue(paginated(uploads))
    spacesApi.getConversations.mockResolvedValue(paginated(conversations))
    spacesApi.getTopics.mockResolvedValue({ data: { data: topics } })
    spacesApi.takeoverSpace.mockResolvedValue({ data: {} })
  })

  it('shows and remembers dismissal of the download prompt for an unbound account', async () => {
    authApi.getDesktopDevices.mockResolvedValue({ data: { data: [] } })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('连接客户端，开始同步聊天')
    expect(wrapper.text()).toContain('适用于 Mac M 系列芯片')
    await wrapper.get('[aria-label="关闭下载提示"]').trigger('click')
    expect(wrapper.text()).not.toContain('连接客户端，开始同步聊天')
    wrapper.unmount()
    const again = mountPage()
    await flushPromises()
    expect(again.text()).not.toContain('连接客户端，开始同步聊天')
  })

  it('hides the prompt after a device is bound and the overview is refreshed', async () => {
    authApi.getDesktopDevices
      .mockResolvedValueOnce({ data: { data: [] } })
      .mockResolvedValue({
        data: { data: [{ device_id: 'mac-1', status: 'active' }] }
      })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('连接客户端，开始同步聊天')
    await button(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('连接客户端，开始同步聊天')
  })

  it('does not show the prompt when the device lookup fails', async () => {
    authApi.getDesktopDevices.mockRejectedValue(new Error('offline'))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).not.toContain('连接客户端，开始同步聊天')
  })

  it('loads the API data and shows four correctly named metrics', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(spacesApi.getSpaces).toHaveBeenCalledOnce()
    expect(spacesApi.getEvents).toHaveBeenCalledWith(spaceId, {
      status: 'open',
      page_size: 100
    })
    expect(spacesApi.getEvents).toHaveBeenCalledWith(spaceId, {
      status: 'in_progress',
      page_size: 100
    })
    expect(spacesApi.getReports).toHaveBeenCalledWith(spaceId, {
      page_size: 20
    })
    expect(spacesApi.getUploads).toHaveBeenCalledWith(spaceId, {
      page_size: 20
    })
    expect(spacesApi.getConversations).toHaveBeenCalledWith(spaceId, {
      page_size: 100
    })
    expect(spacesApi.getTopics).toHaveBeenCalledWith(spaceId)
    expectMetric(wrapper, '云端会话', '3')
    expectMetric(wrapper, '未完成事件', '6')
    expectMetric(wrapper, '主题订阅', '2')
    expectMetric(wrapper, '会话消息', '1,253')
  })

  it('does not mislabel accumulated messages as weekly', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).not.toContain('本周消息')
  })

  it('does not infer device presence from a previous upload', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).not.toContain('在线')
  })

  it('shows only the first five unfinished events and opens the chosen event', async () => {
    const wrapper = mountPage()
    await flushPromises()

    for (const title of [
      '待处理事件一',
      '待处理事件二',
      '待处理事件三',
      '待处理事件四',
      '待处理事件五'
    ]) {
      expect(wrapper.text()).toContain(title)
    }
    expect(wrapper.text()).not.toContain('已完成事件')
    expect(wrapper.text()).not.toContain('待处理事件六')
    expect(button(wrapper, '待处理事件一').text()).toContain('客户')
    await button(wrapper, '待处理事件二').trigger('click')
    expect(push).toHaveBeenCalledWith('/spaces/3/analysis?event=3')
  })

  it('shows the latest four syncs and a preview of the latest report', async () => {
    const wrapper = mountPage()
    await flushPromises()

    for (const id of [101, 102, 103, 104])
      expect(wrapper.text()).toContain(`#${id}`)
    expect(wrapper.text()).not.toContain('#105')
    expect(wrapper.text()).toContain('解析中')
    expect(wrapper.text()).toContain('最新客户报告')
    expect(wrapper.text()).toContain('这是来自接口的报告正文。')
    expect(wrapper.text()).not.toContain('较早的报告')
    await button(wrapper, '最新客户报告').trigger('click')
    expect(push).toHaveBeenCalledWith('/spaces/3/analysis?tab=reports')
    await button(wrapper, '全部报告').trigger('click')
    expect(push).toHaveBeenCalledWith('/spaces/3/analysis?tab=reports')
  })

  it('limits the report preview instead of rendering an unbounded body', async () => {
    spacesApi.getReports.mockResolvedValue(
      paginated([
        { ...reports[0], body: `报告开头${'很长的正文'.repeat(500)}报告结尾` }
      ])
    )
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('报告开头')
    expect(wrapper.text().includes('报告结尾')).toBe(false)
  })

  it('navigates from metrics and overview actions using the existing routes', async () => {
    const wrapper = mountPage()
    await flushPromises()

    for (const [label, route] of [
      ['云端会话', '/spaces/3/chats'],
      ['未完成事件', '/spaces/3/analysis'],
      ['主题订阅', '/spaces/3/topics'],
      ['会话消息', '/spaces/3/operations'],
      ['全部事件', '/spaces/3/analysis'],
      ['同步记录', '/spaces/3/operations'],
      ['去问答', '/spaces/3/analysis?panel=ask']
    ]) {
      await button(wrapper, label).trigger('click')
      expect(push).toHaveBeenLastCalledWith(route)
    }
  })

  it('refreshes from the API and shows the updated values', async () => {
    const wrapper = mountPage()
    await flushPromises()
    spacesApi.getConversations.mockResolvedValue(
      paginated([{ id: 14, message_count: 42 }])
    )
    spacesApi.getEvents.mockResolvedValue(paginated([]))

    await button(wrapper, '刷新').trigger('click')
    await flushPromises()

    expect(spacesApi.getSpaces).toHaveBeenCalledTimes(2)
    expect(spacesApi.getConversations).toHaveBeenCalledTimes(2)
    expectMetric(wrapper, '云端会话', '1')
    expectMetric(wrapper, '会话消息', '42')
    expectMetric(wrapper, '未完成事件', '0')
    expect(wrapper.text()).toContain('暂无已知状态的未完成事件')
  })

  it('shows honest zero and empty states when the API has no records', async () => {
    spacesApi.getEvents.mockResolvedValue(paginated([]))
    spacesApi.getReports.mockResolvedValue(paginated([]))
    spacesApi.getUploads.mockResolvedValue(paginated([]))
    spacesApi.getConversations.mockResolvedValue(paginated([]))
    spacesApi.getTopics.mockResolvedValue({ data: { data: [] } })
    const wrapper = mountPage()
    await flushPromises()

    for (const label of ['云端会话', '未完成事件', '主题订阅', '会话消息']) {
      expectMetric(wrapper, label, '0')
    }
    expect(wrapper.text()).toContain('暂无已知状态的未完成事件')
    expect(wrapper.text()).toContain('还没有报告')
    expect(wrapper.text()).toContain('暂无同步记录')
    expect(wrapper.text()).not.toContain('在线')
  })

  it('displays an API error and clears it after a successful refresh', async () => {
    spacesApi.getReports.mockRejectedValueOnce({
      response: { data: { detail: '报告加载失败' } }
    })
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('报告加载失败')
    await button(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('最新客户报告')
  })

  it.each([
    ['空间', 'getSpaces'],
    ['报告', 'getReports'],
    ['同步', 'getUploads'],
    ['会话', 'getConversations'],
    ['主题', 'getTopics']
  ])(
    'retains loaded content when refreshing fails for %s',
    async (_label, method) => {
      const wrapper = mountPage()
      await flushPromises()
      const updated = wrapper.find('.updated-at').text()
      spacesApi[method].mockRejectedValueOnce(new Error('network error'))
      await button(wrapper, '刷新').trigger('click')
      await flushPromises()

      expect(wrapper.find('[role="alert"]').text()).toContain('可能已过期')
      expectMetric(wrapper, '云端会话', '3')
      expectMetric(wrapper, '未完成事件', '6')
      expectMetric(wrapper, '主题订阅', '2')
      expectMetric(wrapper, '会话消息', '1,253')
      expect(wrapper.text()).toContain('待处理事件一')
      expect(wrapper.text()).toContain('最新客户报告')
      expect(wrapper.text()).toContain('#101')
      expect(wrapper.find('.updated-at').text()).toBe(updated)
    }
  )

  it('updates successful sources while keeping a failed source from the previous refresh', async () => {
    const wrapper = mountPage()
    await flushPromises()
    spacesApi.getReports.mockRejectedValueOnce(new Error('network error'))
    spacesApi.getConversations.mockResolvedValueOnce(
      paginated([{ id: 15, message_count: 42 }])
    )
    await button(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('报告加载失败')
    expect(wrapper.text()).toContain('最新客户报告')
    expectMetric(wrapper, '云端会话', '1')
    expectMetric(wrapper, '会话消息', '42')
  })

  it.each(['open', 'in_progress'])(
    'retains the %s event source when its refresh fails',
    async (failedStatus) => {
      const wrapper = mountPage()
      await flushPromises()
      spacesApi.getEvents.mockImplementation((_id, { status }) =>
        status === failedStatus
          ? Promise.reject(new Error('network error'))
          : Promise.resolve(paginated([]))
      )
      await button(wrapper, '刷新').trigger('click')
      await flushPromises()
      expect(wrapper.find('[role="alert"]').text()).toContain('可能已过期')
      expect(wrapper.text()).toContain(
        failedStatus === 'open' ? '待处理事件一' : '待处理事件二'
      )
      expectMetric(wrapper, '未完成事件', failedStatus === 'open' ? '5' : '1')
      expect(wrapper.text()).toContain('最新客户报告')
    }
  )

  it('shows available sources and unknown placeholders on a partial first load', async () => {
    spacesApi.getEvents.mockImplementation((_id, { status }) =>
      status === 'in_progress'
        ? Promise.reject(new Error('network error'))
        : Promise.resolve(
            paginated(events.filter((event) => event.status === status))
          )
    )
    spacesApi.getUploads.mockRejectedValue(new Error('network error'))
    spacesApi.getReports.mockRejectedValue(new Error('network error'))
    spacesApi.getTopics.mockRejectedValue(new Error('network error'))
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('加载失败')
    expectMetric(wrapper, '未完成事件', '—')
    expectMetric(wrapper, '主题订阅', '—')
    expectMetric(wrapper, '云端会话', '3')
    expect(wrapper.text()).toContain('待处理事件一')
    expect(wrapper.text()).toContain('报告暂不可用')
    expect(wrapper.text()).toContain('同步记录暂不可用')
    expect(wrapper.text()).not.toContain('暂无同步记录')
    expect(wrapper.text()).not.toContain('还没有报告')
    expect(wrapper.find('.updated-at').exists()).toBe(false)
  })

  it('keeps content visible during a slow refresh', async () => {
    const wrapper = mountPage()
    await flushPromises()
    let finish
    spacesApi.getReports.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    await button(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('最新客户报告')
    expect(wrapper.text()).toContain('待处理事件一')
    finish(paginated(reports))
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('merges the first pages of known unfinished statuses instead of filtering the first page of all events', async () => {
    const done = Array.from({ length: 120 }, (_, index) => ({
      id: 500 + index,
      status: 'done',
      title: '已完成事件样例',
      last_activity_at: '2026-11-11T00:00:00Z'
    }))
    const open = Array.from({ length: 120 }, (_, index) => ({
      id: 300 - index,
      status: 'open',
      title: `待处理${index}`,
      last_activity_at: new Date(
        Date.UTC(2026, 10, 9) - index * 1000
      ).toISOString()
    }))
    const ongoing = {
      id: 800,
      status: 'in_progress',
      title: '最新进行中',
      last_activity_at: '2026-11-10T00:00:00Z'
    }
    const unknown = {
      id: 900,
      status: null,
      title: '未知状态',
      last_activity_at: '2026-11-12T00:00:00Z'
    }
    const dataset = [...done, unknown, ...open, ongoing]
    spacesApi.getEvents.mockImplementation((_id, { status, page_size }) => {
      const filtered = dataset.filter((event) => event.status === status)
      const response = paginated(filtered.slice(0, page_size))
      response.data.data.pagination.total = filtered.length
      response.data.data.pagination.next =
        filtered.length > page_size ? '?page=2' : null
      return Promise.resolve(response)
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(spacesApi.getEvents).toHaveBeenCalledTimes(2)
    expectMetric(wrapper, '未完成事件', '100')
    expect(wrapper.text()).toContain('最多加载前 100 个已知状态的未完成事件')
    expect(wrapper.findAll('.event-row')[0].text()).toContain('最新进行中')
    expect(wrapper.text()).toContain('待处理0')
    expect(wrapper.text()).not.toContain('已完成事件样例')
    expect(wrapper.text()).not.toContain('未知状态')
  })

  it('orders equal-millisecond event times using backend microsecond precision', async () => {
    spacesApi.getEvents.mockImplementation((_id, { status }) =>
      Promise.resolve(
        paginated(
          status === 'open'
            ? [
                {
                  id: 99,
                  status,
                  title: '较早微秒',
                  last_activity_at: '2026-11-10T00:00:00.123001Z'
                }
              ]
            : [
                {
                  id: 1,
                  status,
                  title: '较新微秒',
                  last_activity_at: '2026-11-10T00:00:00.123999Z'
                }
              ]
        )
      )
    )
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.event-row')[0].text()).toContain('较新微秒')
  })

  it('does not treat a malformed response as an empty list', async () => {
    spacesApi.getConversations.mockResolvedValue({ data: { data: {} } })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('会话加载失败')
    expectMetric(wrapper, '云端会话', '—')
    expectMetric(wrapper, '会话消息', '—')
    expect(wrapper.text()).toContain('最新客户报告')
  })

  it('does not start resource requests if the initial space check fails', async () => {
    spacesApi.getSpaces.mockRejectedValueOnce(new Error('network error'))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.find('.stats').exists()).toBe(false)
    expect(spacesApi.getEvents).not.toHaveBeenCalled()
  })

  it('does not replace missing or invalid counts with zero', async () => {
    spacesApi.getConversations.mockResolvedValue(
      paginated([{ id: 1, message_count: null }])
    )
    spacesApi.getUploads.mockResolvedValue(
      paginated([{ id: 4, status: 'completed' }])
    )
    spacesApi.getTopics.mockResolvedValue({
      data: { data: [{ id: 5, enabled: null }] }
    })
    const wrapper = mountPage()
    await flushPromises()
    expectMetric(wrapper, '会话消息', '—')
    expect(wrapper.text()).toContain('未知 条消息')
    expect(wrapper.text()).not.toContain('0 条消息')
    expect(button(wrapper, '主题订阅').text()).toContain('启用状态未知')
  })

  it('keeps a late response from an old space from overwriting the current space', async () => {
    let finishOldEvents
    spacesApi.getEvents.mockImplementation((id, { status }) => {
      if (status === 'in_progress') return Promise.resolve(paginated([]))
      if (id === 3)
        return new Promise((resolve) => {
          finishOldEvents = resolve
        })
      return Promise.resolve(
        paginated([{ id: 44, title: '新空间事件', status: 'open' }])
      )
    })
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.setProps({ spaceId: 4 })
    await flushPromises()
    expect(wrapper.text()).toContain('新空间事件')
    finishOldEvents(
      paginated([{ id: 55, title: '旧空间事件', status: 'open' }])
    )
    await flushPromises()
    expect(wrapper.text()).toContain('新空间事件')
    expect(wrapper.text()).not.toContain('旧空间事件')
    await button(wrapper, '新空间事件').trigger('click')
    expect(push).toHaveBeenLastCalledWith('/spaces/4/analysis?event=44')
  })

  it('requests takeover before loading a global-admin workspace', async () => {
    spacesApi.getSpaces
      .mockResolvedValueOnce({
        data: { data: [{ ...space, is_global_admin: true }] }
      })
      .mockResolvedValueOnce({
        data: {
          data: [
            { ...space, is_global_admin: true, admin_takeover_active: true }
          ]
        }
      })
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('准备个人工作台')
    expect(spacesApi.getEvents).not.toHaveBeenCalled()
    await button(wrapper, '开始准备').trigger('click')
    await flushPromises()

    expect(spacesApi.takeoverSpace).toHaveBeenCalledWith(
      spaceId,
      'Prepare default personal workspace'
    )
    expect(spacesApi.getEvents).toHaveBeenCalledWith(spaceId, {
      status: 'open',
      page_size: 100
    })
    expect(spacesApi.getEvents).toHaveBeenCalledWith(spaceId, {
      status: 'in_progress',
      page_size: 100
    })
    expect(wrapper.text()).not.toContain('准备个人工作台')
    expectMetric(wrapper, '云端会话', '3')
  })
})
