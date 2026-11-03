// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AppSidebar from './AppSidebar.vue'
vi.mock('vue-router', () => ({ useRoute: () => ({ path: '/spaces/42/analysis', name: 'SpaceAnalysis', params: { spaceId: '42' }, query: {} }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: key => ({ 'spaces.personalWorkspace': '工作台', 'spaces.conversationRecords': '会话记录', 'spaces.mailConversations': '对话列表', 'spaces.menuTitle': '空间' })[key] || key }) }))
vi.mock('@/api/relay', () => ({ relayApi: { getApps: vi.fn().mockResolvedValue([]) } }))
vi.mock('@/composables/useAccountSummary', () => ({ useAccountSummary: () => ({ ensureLoaded: vi.fn(), unfiledInvoices: { value: 0 }, openTodos: { value: 0 } }) }))
vi.mock('./UserMenu.vue', () => ({ default: { template: '<span />' } }))
const RouterLink = { props: ['to'], template: '<a :href="typeof to === \'string\' ? to : to.path"><slot /></a>' }
describe('workspace navigation', () => {
  it('shows function names and keeps the current space when navigating', async () => {
    const wrapper = mount(AppSidebar, { global: { stubs: { RouterLink } } })
    await flushPromises()
    const links = wrapper.findAll('a')
    expect(wrapper.find('button.nav-parent').text()).toContain('工作台')
    expect(links.find(link => link.text() === '会话').attributes('href')).toBe('/spaces/42/chats')
    expect(links.some(link => link.text() === '空间')).toBe(false)
    expect(links.some(link => link.text() === '对话列表')).toBe(true)
    expect(links.some(link => link.text() === '主题订阅')).toBe(true)
  })
})
