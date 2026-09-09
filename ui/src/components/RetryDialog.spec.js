// @vitest-environment happy-dom

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RetryDialog from './RetryDialog.vue'

const { getAvailableScenes, getPreferences } = vi.hoisted(() => ({
  getAvailableScenes: vi.fn(),
  getPreferences: vi.fn()
}))

vi.mock('@/api/auth', () => ({
  authApi: { getAvailableScenes }
}))

vi.mock('@/api/settings', () => ({
  settingsApi: { getPreferences }
}))

vi.mock('vue-i18n', async () => {
  const { ref } = await vi.importActual('vue')
  const messages = {
    'auth.selectScene': 'Select a scene',
    'common.cancel': 'Cancel',
    'common.loading': 'Loading',
    'retry.confirmRetry': 'Retry',
    'retry.dialogTitle': 'Retry Chat Processing',
    'retry.expenseDialogTitle': 'Retry Expense Processing',
    'retry.expenseFlowTitle': 'Expense invoice recognition',
    'retry.expenseFlowDescription': 'Expense will reprocess this email.',
    'retry.conversationFlowTitle': 'Conversation processing',
    'retry.conversationFlowDescription':
      'This email will be reprocessed as a conversation.',
    'retry.forceMode': 'Force Retry',
    'retry.forceModeRequired':
      'Required because this conversation has already completed.',
    'retry.forceModeWarning': 'Force retry clears previous results.',
    'retry.useDefaultLanguage': 'Use default language',
    'settings.language': 'Language',
    'settings.languages.en': 'English',
    'settings.languages.es': 'Spanish',
    'settings.languages.zh-CN': 'Chinese',
    'settings.scene': 'Scene'
  }

  return {
    useI18n: () => ({
      locale: ref('en'),
      t: (key) => messages[key] || key
    })
  }
})

const mountDialog = async (status, retryFlow = 'conversation') => {
  const wrapper = mount(RetryDialog, {
    props: { show: true, status, retryFlow },
    global: {
      stubs: {
        BaseButton: {
          template: '<button><slot /></button>'
        },
        BaseModal: {
          props: ['title'],
          template:
            '<section><h1>{{ title }}</h1><slot /><slot name="footer" /></section>'
        }
      }
    }
  })

  await flushPromises()
  return wrapper
}

describe('RetryDialog', () => {
  beforeEach(() => {
    getAvailableScenes.mockResolvedValue({
      data: { data: [{ key: 'general', name: 'General' }] }
    })
    getPreferences.mockResolvedValue({ language: 'en-US', scene: 'general' })
  })

  it('explains mandatory force retry without rendering a disabled checkbox', async () => {
    const wrapper = await mountDialog('success')

    expect(wrapper.find('#force-retry').exists()).toBe(false)
    expect(
      wrapper.get('[data-testid="force-retry-required"]').text()
    ).toContain('Required because this conversation has already completed.')

    await wrapper.get('button:last-of-type').trigger('click')

    expect(wrapper.emitted('confirm')).toEqual([
      [{ language: 'en-US', scene: 'general', force: true }]
    ])
  })

  it('keeps force retry optional for conversations that have not completed', async () => {
    const wrapper = await mountDialog('failed')
    const checkbox = wrapper.get('#force-retry')

    expect(checkbox.attributes('disabled')).toBeUndefined()
    await checkbox.setValue(true)
    await wrapper.get('button:last-of-type').trigger('click')

    expect(wrapper.emitted('confirm')).toEqual([
      [{ language: 'en-US', scene: 'general', force: true }]
    ])
  })

  it('explains the Expense flow and disables irrelevant controls', async () => {
    const wrapper = await mountDialog('failed', 'expense')

    expect(wrapper.text()).toContain('Retry Expense Processing')
    expect(wrapper.text()).toContain('Expense invoice recognition')
    expect(wrapper.text()).toContain('Expense will reprocess this email.')
    expect(wrapper.findAll('select')).toHaveLength(2)
    expect(
      wrapper
        .findAll('select')
        .every((select) => select.attributes('disabled') !== undefined)
    ).toBe(true)

    await wrapper.get('button:last-of-type').trigger('click')

    expect(wrapper.emitted('confirm')).toEqual([
      [{ language: null, scene: null, force: false }]
    ])
  })

  it('keeps language and scene active for the conversation flow', async () => {
    const wrapper = await mountDialog('failed')

    expect(wrapper.text()).toContain('Retry Chat Processing')
    expect(wrapper.text()).toContain('Conversation processing')
    expect(wrapper.text()).not.toContain('Expense will reprocess this email.')
    expect(
      wrapper
        .findAll('select')
        .every((select) => select.attributes('disabled') === undefined)
    ).toBe(true)
  })
})
