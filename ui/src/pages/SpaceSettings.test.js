// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SpaceSettings from './SpaceSettings.vue'
import { authApi } from '@/api/auth'
import { spacesApi } from '@/api/spaces'

vi.mock('@/components/layout/AppLayout.vue', () => ({
  default: { template: '<div><slot /></div>' }
}))
vi.mock('@/api/auth', () => ({
  authApi: {
    getDesktopDevices: vi.fn(),
    revokeDesktopDevice: vi.fn()
  }
}))
vi.mock('@/api/spaces', () => ({
  spacesApi: {
    getWorkflowConfig: vi.fn(),
    getQuotaUsage: vi.fn(),
    getUploads: vi.fn()
  }
}))

const now = new Date().toISOString()
const device = {
  device_id: 'device-abcdef123456',
  label: 'MacBook Pro · 工作',
  platform: 'macos',
  status: 'active',
  last_seen_at: now,
  created_at: '2026-09-12T09:00:00Z'
}

const mountPage = () => mount(SpaceSettings, { props: { spaceId: 3 } })

describe('SpaceSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authApi.getDesktopDevices.mockResolvedValue({
      data: { data: [device] }
    })
    spacesApi.getWorkflowConfig.mockResolvedValue({
      data: {
        data: {
          auto_process: true,
          processing_paused: false,
          attachment_policy: 'available',
          language: 'zh-CN',
          scene: 'chat',
          version: 3,
          updated_at: '2026-11-01T10:00:00Z'
        }
      }
    })
    spacesApi.getQuotaUsage.mockResolvedValue({
      data: {
        data: {
          quota: {
            storage_limit_bytes: null,
            max_members: null,
            daily_ai_calls: null
          },
          usage: {
            member_count: 3,
            storage_used_bytes: 195035136,
            conversation_count: 12,
            message_count: 9412,
            media_count: 312,
            daily_ai_calls_used: 5
          }
        }
      }
    })
    spacesApi.getUploads.mockResolvedValue({
      data: {
        data: {
          list: [],
          pagination: { next: null }
        }
      }
    })
  })

  it('renders bound devices with platform and presence', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(authApi.getDesktopDevices).toHaveBeenCalled()
    expect(wrapper.text()).toContain('MacBook Pro · 工作')
    expect(wrapper.text()).toContain('macOS')
    expect(wrapper.text()).toContain('在线')
    expect(wrapper.text()).toContain('已绑定设备')
  })

  it('renders the stored processing defaults read-only', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(spacesApi.getWorkflowConfig).toHaveBeenCalledWith(3)
    expect(wrapper.text()).toContain('自动处理')
    expect(wrapper.text()).toContain('开启')
    expect(wrapper.text()).toContain('简体中文')
    expect(wrapper.text()).toContain('v3')
  })

  it('renders real cloud usage numbers', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(spacesApi.getQuotaUsage).toHaveBeenCalledWith(3)
    expect(wrapper.text()).toContain('186 MB')
    expect(wrapper.text()).toContain('9,412 条消息')
    expect(wrapper.text()).toContain('312 个媒体文件')
    expect(wrapper.text()).toContain('5 次')
    expect(wrapper.text()).toContain('未设置上限')
  })

  it('explains the empty state without devices', async () => {
    authApi.getDesktopDevices.mockResolvedValue({ data: { data: [] } })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('还没有登记设备')
    expect(wrapper.text()).toContain('重启客户端')
  })

  it('shows the latest client upload when no device is registered', async () => {
    authApi.getDesktopDevices.mockResolvedValue({ data: { data: [] } })
    spacesApi.getUploads.mockResolvedValue({
      data: {
        data: {
          list: [
            {
              id: 22,
              created_at: '2026-11-03T08:35:00Z',
              platform: 'macos',
              source_provider: 'tauri_upload'
            }
          ],
          pagination: { next: null }
        }
      }
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('已检测到')
    expect(wrapper.text()).toContain('macOS')
  })

  it('revokes a device after confirmation', async () => {
    vi.stubGlobal(
      'confirm',
      vi.fn(() => true)
    )
    authApi.revokeDesktopDevice.mockResolvedValue({ status: 204 })
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.revoke').trigger('click')
    await flushPromises()
    expect(authApi.revokeDesktopDevice).toHaveBeenCalledWith(device.device_id)
    expect(wrapper.text()).not.toContain('MacBook Pro · 工作')
    vi.unstubAllGlobals()
  })
})
