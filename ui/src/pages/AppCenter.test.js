// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import AppCenter from './AppCenter.vue'
import { relayApi } from '@/api/relay'
const { route, push } = vi.hoisted(() => ({ route: { params: {} }, push: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: key => key }) }))
vi.mock('@/api/relay', () => ({ relayApi: { getApps: vi.fn() } }))
vi.mock('@/composables/useToast', () => ({ useToast: () => ({ showError: vi.fn() }) }))
vi.mock('@/store/preferences', () => ({ usePreferencesStore: () => ({ currentLanguage: 'zh-CN' }) }))
vi.mock('@/components/layout/AppLayout.vue', () => ({ default: { template: '<div><slot /></div>' } }))
vi.mock('@/components/layout/PageHeader.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/ui/BaseLoading.vue', () => ({ default: { template: '<div>loading</div>' } }))
vi.mock('@/components/apps/AppCard.vue', () => ({ default: { props: ['name'], template: '<button @click="$emit(\'open\')">{{ name }}</button>' } }))
const render = () => mount(AppCenter, { global: { stubs: { RouterLink: true } } })
describe('space application center', () => {
  beforeEach(() => { vi.clearAllMocks(); route.params = reactive({}) })
  it('requests the team space catalog and does not display account apps', async () => {
    route.params.spaceId = '12'
    relayApi.getApps.mockResolvedValue([])
    const wrapper = render()
    await flushPromises()
    expect(relayApi.getApps).toHaveBeenCalledWith('12')
    expect(wrapper.text()).toContain('apps.noSpaceApps')
    expect(wrapper.text()).not.toContain('发票管理')
  })
  it('uses the legacy personal catalog without a space context', async () => {
    relayApi.getApps.mockResolvedValue([{ key: 'expense', name: 'Expense', name_zh: '发票管理', path: '/apps/expense' }])
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('发票管理')
    await wrapper.find('button').trigger('click')
    expect(push).toHaveBeenCalledWith('/apps/expense')
  })
  it('does not display a late response from the previously selected space', async () => {
    let resolvePersonal
    route.params.spaceId = '1'
    relayApi.getApps.mockImplementation(id => id === '1'
      ? new Promise(resolve => { resolvePersonal = resolve })
      : Promise.resolve([]))
    const wrapper = render()
    route.params.spaceId = '2'
    await flushPromises()
    resolvePersonal([{ key: 'expense', name: 'Expense', name_zh: '发票管理' }])
    await flushPromises()
    expect(wrapper.text()).not.toContain('发票管理')
    expect(wrapper.text()).toContain('apps.noSpaceApps')
  })
  it('shows an error instead of an empty catalog when loading fails', async () => {
    relayApi.getApps.mockRejectedValue(new Error('offline'))
    const wrapper = render()
    await flushPromises()
    expect(wrapper.find('[role=alert]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('apps.noSpaceApps')
  })
})
