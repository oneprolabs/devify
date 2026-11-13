// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SpaceOperations from './SpaceOperations.vue'
import { authApi } from '@/api/auth'
import { spacesApi } from '@/api/spaces'

vi.mock('@/components/layout/AppLayout.vue', () => ({
  default: { template: '<div><slot /></div>' }
}))
vi.mock('@/api/auth', () => ({
  authApi: {
    getDesktopDevices: vi.fn()
  }
}))
vi.mock('@/api/spaces', () => ({
  spacesApi: {
    getUploads: vi.fn()
  }
}))

const uploads = [
  {
    id: 429,
    status: 'completed',
    created_at: '2026-11-04T11:41:00Z',
    archive_received_at: '2026-11-04T11:41:01Z',
    parse_started_at: '2026-11-04T11:41:02Z',
    completed_at: '2026-11-04T11:41:05Z',
    message_count: 412,
    duplicate_count: 0,
    conversation_count: 9,
    image_count: 14,
    archive_size: 1024,
    device_id: 'mac-1',
    trigger: 'manual',
    error_message: '',
    analysis_summary: {
      state: 'running',
      job_count: 1,
      event_count: 0,
      running: true,
      failed: false,
      partial: false,
      retried: false,
      duration_seconds: null
    }
  },
  {
    id: 391,
    status: 'completed',
    created_at: '2026-10-28T22:06:00Z',
    archive_received_at: '2026-10-28T22:06:02Z',
    parse_started_at: '2026-10-28T22:06:03Z',
    completed_at: '2026-10-28T22:07:00Z',
    message_count: 0,
    duplicate_count: 2,
    conversation_count: 0,
    image_count: 0,
    archive_size: 2048,
    device_id: 'win-1',
    trigger: 'scheduled',
    error_message: '',
    analysis_summary: {
      state: '',
      job_count: 0,
      event_count: 0,
      running: false,
      failed: false,
      partial: false,
      retried: false,
      duration_seconds: null
    }
  }
]

const mountPage = () => mount(SpaceOperations, { props: { spaceId: 3 } })

describe('SpaceOperations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authApi.getDesktopDevices.mockResolvedValue({
      data: {
        data: [
          {
            device_id: 'mac-1',
            label: 'MacBook Pro · 工作',
            platform: 'macos',
            status: 'active',
            last_seen_at: '2026-11-04T11:41:00Z'
          },
          {
            device_id: 'win-1',
            label: 'Windows 台式机 · 家',
            platform: 'windows',
            status: 'active',
            last_seen_at: '2026-10-28T22:06:00Z'
          }
        ]
      }
    })
    spacesApi.getUploads.mockResolvedValue({
      data: {
        data: {
          list: uploads,
          pagination: { next: null }
        }
      }
    })
  })

  it('renders sync rows with the device that produced them', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(spacesApi.getUploads).toHaveBeenCalledWith(3, {
      page_size: 100,
      page: 1
    })
    expect(wrapper.text()).toContain('MacBook Pro · 工作')
    expect(wrapper.text()).toContain('Windows 台式机 · 家')
    expect(wrapper.text()).toContain('9 会话 · 412 条')
    expect(wrapper.text()).toContain('关联分析中')
    expect(wrapper.text()).toContain('手动')
    expect(wrapper.text()).toContain('定时')
    expect(wrapper.text()).toContain('无变化')
  })

  it('expands a record into real pipeline stages', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.sync-row:not(.sync-head)').trigger('click')
    const stages = wrapper.find('.stages')
    expect(stages.exists()).toBe(true)
    expect(stages.text()).toContain('412 条消息 · 9 个会话 · 14 张图片')
    expect(stages.text()).toContain('归档 1 KB 已送达云端')
    expect(stages.text()).toContain('会话 → 消息，归 412 条')
    expect(stages.findAll('.stage')).toHaveLength(6)
  })

  it('does not present unknown upload and parsing counts as zero', async () => {
    const old = new Date(Date.now() - 30 * 60 * 1000).toISOString()
    spacesApi.getUploads.mockResolvedValue({
      data: {
        data: {
          list: [
            {
              id: 1,
              status: 'uploading',
              created_at: old,
              updated_at: old,
              device_id: 'mac-1'
            },
            {
              id: 2,
              status: 'processing',
              created_at: old,
              archive_received_at: old,
              device_id: 'mac-1'
            }
          ],
          pagination: { next: null }
        }
      }
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('上传状态待确认')
    expect(wrapper.text()).toContain('等待解析')
    expect(wrapper.text()).toContain('等待解析较长')
    expect(wrapper.text()).not.toContain('0 条新消息')
    await wrapper.findAll('.sync-row:not(.sync-head)')[1].trigger('click')
    expect(wrapper.find('.stages').text()).toContain('归档已接收，数量待解析')
    expect(wrapper.find('.stages').text()).not.toContain('本次没有图片')
  })

  it('refreshes task state while keeping the expanded record open', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    let wrapper
    try {
      const waiting = { ...uploads[0], status: 'processing', message_count: 0, worker_started_at: new Date().toISOString() }
      spacesApi.getUploads.mockResolvedValue({
        data: { data: { list: [waiting], pagination: { next: null } } }
      })
      wrapper = mountPage()
      await flushPromises()
      await wrapper.find('.sync-row:not(.sync-head)').trigger('click')
      expect(wrapper.text()).toContain('解析统计中')
      spacesApi.getUploads.mockResolvedValue({
        data: { data: { list: [uploads[0]], pagination: { next: null } } }
      })
      await vi.advanceTimersByTimeAsync(15000)
      await flushPromises()
      expect(wrapper.text()).toContain('9 会话 · 412 条')
      expect(wrapper.find('.stages').exists()).toBe(true)
    } finally {
      wrapper?.unmount()
      vi.useRealTimers()
    }
  })

  it('filters records by device', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const buttons = wrapper.findAll('.device-seg button')
    expect(buttons).toHaveLength(3)
    await buttons[2].trigger('click')
    const rows = wrapper.findAll('.sync-row:not(.sync-head)')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('Windows 台式机 · 家')
    expect(rows[0].text()).not.toContain('MacBook Pro · 工作')
  })

  it('keeps the device tabs visible before a device uploads', async () => {
    spacesApi.getUploads.mockResolvedValue({
      data: { data: { list: [], pagination: { next: null } } }
    })
    const wrapper = mountPage()
    await flushPromises()
    const buttons = wrapper.findAll('.device-seg button')
    expect(buttons.map((button) => button.text())).toEqual([
      '全部设备',
      'MacBook Pro',
      'Windows 台式机'
    ])
  })

  it('labels historical desktop uploads without a device id', async () => {
    spacesApi.getUploads.mockResolvedValue({
      data: {
        data: {
          list: [
            {
              ...uploads[1],
              id: 100,
              device_id: '',
              source_provider: 'tauri_upload',
              platform: 'macos'
            }
          ],
          pagination: { next: null }
        }
      }
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('桌面客户端 · macOS')
    const tabs = wrapper.findAll('.device-seg button')
    expect(tabs.map((tab) => tab.text())).toContain('未记录设备')
    await tabs[3].trigger('click')
    expect(wrapper.findAll('.sync-row:not(.sync-head)')).toHaveLength(1)
  })

  it('shows an honest empty state without uploads', async () => {
    spacesApi.getUploads.mockResolvedValue({
      data: { data: { list: [], pagination: { next: null } } }
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('还没有同步记录')
  })
})
