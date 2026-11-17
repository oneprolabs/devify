import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const {
  createSubscription,
  updateSubscription,
  testSubscription
} = vi.hoisted(() => ({
  createSubscription: vi.fn(),
  updateSubscription: vi.fn(),
  testSubscription: vi.fn()
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key) => key })
}))

vi.mock('@/api/relay', () => ({
  relayApi: {
    createSubscription,
    updateSubscription,
    testSubscription
  }
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn()
  })
}))

import { useRelayEditor } from './useRelayEditor'

describe('useRelayEditor GitHub Issue target', () => {
  beforeEach(() => {
    createSubscription.mockReset()
    updateSubscription.mockReset()
    testSubscription.mockReset()
  })

  function createEditor() {
    return useRelayEditor({
      reloadAll: vi.fn(),
      activeTab: ref('channels')
    })
  }

  it('builds a GitHub test payload with repo credentials and mappings', () => {
    const { editorForm, buildTestPayload } = createEditor()
    editorForm.target_type = 'github_issue'
    editorForm.language = 'English'
    editorForm.githubConfig.repo = 'oneprolabs/devify'
    editorForm.githubConfig.token = 'github-token'
    editorForm.githubConfig.labels_text = 'relay\nneeds-review'
    editorForm.githubConfig.assignees_text = 'octocat\nhubot'

    const payload = buildTestPayload()

    expect(payload.subscription.config).toMatchObject({
      issue_engine: 'github_issue',
      language: 'English',
      github: {
        repo: 'oneprolabs/devify',
        token: 'github-token',
        labels: ['relay', 'needs-review'],
        assignees: ['octocat', 'hubot']
      }
    })
    expect(payload.artifact_snapshot).toMatchObject({
      summary_title: 'devify 测试摘要',
      summary_content: 'devify 测试描述',
      language: 'Chinese'
    })
  })

  it('includes Jira project defaults in the test delivery payload', () => {
    const { editorForm, buildTestPayload } = createEditor()
    editorForm.target_type = 'jira'
    editorForm.jiraConfig.url = 'https://jira.example.com'
    editorForm.jiraConfig.username = 'test-user'
    editorForm.jiraConfig.api_token = 'test-token'
    editorForm.jiraConfig.project_key = 'KAN'
    editorForm.jiraConfig.issue_type_default = 'Task'
    editorForm.jiraConfig.priority_default = 'Medium'

    const payload = buildTestPayload()

    expect(payload.subscription.config).toMatchObject({
      jira: {
        url: 'https://jira.example.com',
        username: 'test-user',
        api_token: 'test-token'
      },
      fields: {
        project_key_config: { default: 'KAN' },
        issue_type_config: { default: 'Task' },
        priority_config: { default: 'Medium' }
      }
    })
  })

  it('restores GitHub config when editing a subscription', () => {
    const { editorForm, editSubscription } = createEditor()

    editSubscription({
      id: 22,
      target_type: 'github_issue',
      name: 'Devify GitHub',
      enabled: true,
      strategies: {},
      field_mappings: {},
      config: {
        language: 'English',
        github: {
          repo: 'oneprolabs/devify',
          token: 'github-token',
          labels: ['relay', 'bug'],
          assignees: ['octocat']
        }
      }
    })

    expect(editorForm.githubConfig).toEqual({
      repo: 'oneprolabs/devify',
      token: 'github-token',
      labels_text: 'relay\nbug',
      assignees_text: 'octocat'
    })
  })

  it('persists GitHub config using string arrays', async () => {
    createSubscription.mockResolvedValue({ id: 22 })
    const { editorForm, persistEditor } = createEditor()
    editorForm.target_type = 'github_issue'
    editorForm.name = 'Devify GitHub'
    editorForm.githubConfig.repo = 'oneprolabs/devify'
    editorForm.githubConfig.token = 'github-token'
    editorForm.githubConfig.labels_text = 'relay\nfeature'
    editorForm.githubConfig.assignees_text = 'octocat'

    await persistEditor()

    expect(createSubscription).toHaveBeenCalledWith(
      expect.objectContaining({
        target_type: 'github_issue',
        config: expect.objectContaining({
          issue_engine: 'github_issue',
          github: {
            repo: 'oneprolabs/devify',
            token: 'github-token',
            labels: ['relay', 'feature'],
            assignees: ['octocat']
          }
        })
      })
    )
  })

  it('allows saving after a successful test delivery', async () => {
    testSubscription.mockResolvedValue({ external_id: 'TEST-1' })
    const { editorForm, runEditorTest, editorTestPassed, editorCanSave } =
      createEditor()
    editorForm.target_type = 'github_issue'
    editorForm.name = 'Devify GitHub'
    editorForm.githubConfig.repo = 'oneprolabs/devify'
    editorForm.githubConfig.token = 'github-token'

    await runEditorTest()

    expect(testSubscription).toHaveBeenCalledOnce()
    expect(editorTestPassed.value).toBe(true)
    expect(editorCanSave.value).toBe(true)
  })

  it('does not approve edits made while the test is running', async () => {
    let resolveTest
    testSubscription.mockReturnValue(
      new Promise((resolve) => {
        resolveTest = resolve
      })
    )
    const { editorForm, runEditorTest, editorTestPassed, editorCanSave } =
      createEditor()
    editorForm.target_type = 'github_issue'
    editorForm.githubConfig.repo = 'oneprolabs/devify'
    editorForm.githubConfig.token = 'github-token'

    const testPromise = runEditorTest()
    editorForm.name = 'Changed after test started'
    resolveTest({ external_id: 'TEST-1' })
    await testPromise

    expect(editorTestPassed.value).toBe(false)
    expect(editorCanSave.value).toBe(false)
  })
})
