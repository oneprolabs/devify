// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PersonalWorkspace from './PersonalWorkspace.vue'
import { spacesApi } from '@/api/spaces'
const replace = vi.fn()
const route = { query: {} }
vi.mock('@/components/layout/AppLayout.vue', () => ({ default: { template: '<div><slot /></div>' } }))
vi.mock('@/api/spaces', () => ({ spacesApi: { getSpaces: vi.fn() } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace }), useRoute: () => route }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: key => key }) }))
describe('PersonalWorkspace', () => {
  beforeEach(() => { vi.clearAllMocks(); route.query = {}; replace.mockResolvedValue() })
  it('opens the user’s personal space rather than a team or another personal space', async () => {
    spacesApi.getSpaces.mockResolvedValue({ data: { data: [{ id: 1, kind: 'team' }, { id: 2, kind: 'personal', is_personal_owner: false }, { id: 3, kind: 'personal', is_personal_owner: true }] } })
    mount(PersonalWorkspace, { global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(replace).toHaveBeenCalledWith('/spaces/3/overview')
  })
  it('opens conversation records in the personal space on request', async () => {
    route.query = { view: 'chats' }
    spacesApi.getSpaces.mockResolvedValue({ data: { data: [{ id: 3, kind: 'personal', is_personal_owner: true }] } })
    mount(PersonalWorkspace, { global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(replace).toHaveBeenCalledWith('/spaces/3/chats')
  })
  it('offers retry rather than choosing another space when no personal space exists', async () => {
    spacesApi.getSpaces.mockResolvedValue({ data: { data: [{ id: 1, kind: 'team' }] } })
    const wrapper = mount(PersonalWorkspace, { global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(replace).not.toHaveBeenCalled()
    expect(wrapper.find('[role=alert]').exists()).toBe(true)
  })
})
