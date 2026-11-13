// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import VoiceBubble from './VoiceBubble.vue'
import api from '@/api'

vi.mock('@/api', () => ({ default: { get: vi.fn() } }))

describe('VoiceBubble', () => {
  afterEach(() => vi.restoreAllMocks())

  it('fetches private audio and plays with one click, then pauses', async () => {
    api.get.mockResolvedValue({ data: new Blob(['audio']) })
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:voice')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const play = vi
      .spyOn(HTMLMediaElement.prototype, 'play')
      .mockResolvedValue()
    const pause = vi
      .spyOn(HTMLMediaElement.prototype, 'pause')
      .mockImplementation(() => {})
    const wrapper = mount(VoiceBubble, { props: { url: '/v1/media/1' } })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('/v1/media/1', {
      responseType: 'blob'
    })
    expect(play).toHaveBeenCalledOnce()
    expect(wrapper.get('.voice-icon').classes()).toContain('playing')
    await wrapper.get('button').trigger('click')
    expect(pause).toHaveBeenCalledOnce()
    expect(wrapper.get('.voice-icon').classes()).not.toContain('playing')
    wrapper.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:voice')
  })

  it('shows a useful error when audio cannot be fetched', async () => {
    api.get.mockRejectedValue(new Error('offline'))
    const wrapper = mount(VoiceBubble, { props: { url: '/v1/media/1' } })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('语音加载失败')
    wrapper.unmount()
  })

  it('rounds audio duration to the nearest second', async () => {
    const wrapper = mount(VoiceBubble, { props: { url: '/v1/media/1' } })
    const audio = wrapper.get('audio')
    Object.defineProperty(audio.element, 'duration', { value: 2.1 })
    await audio.trigger('loadedmetadata')
    expect(wrapper.text()).toContain('2″')
    wrapper.unmount()
  })
})
