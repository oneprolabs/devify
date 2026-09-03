/**
 * The delivery channel types Relay can talk to.
 *
 * Kept in one place because three views describe the same set: the type
 * gallery, the channel rail's grouping, and the row labels. Adding a fourth
 * type means one entry here, not a fourth switch statement.
 */

export const TYPE_LABEL_KEYS = {
  jira: 'relay.targetJira',
  github_issue: 'relay.targetGitHub',
  feishu_bitable: 'relay.targetFeishu'
}

export const TYPE_INITIALS = {
  jira: 'JR',
  github_issue: 'GH',
  feishu_bitable: 'FS'
}

export const CHANNEL_CATEGORIES = [
  {
    key: 'tracker',
    labelKey: 'relay.categoryTracker',
    types: ['jira', 'github_issue']
  },
  {
    key: 'table',
    labelKey: 'relay.categoryTable',
    types: ['feishu_bitable']
  }
]

/**
 * What each type can actually do, which is what the gallery card promises.
 * Feishu can be told to link but only records the intent, so it is marked
 * partial rather than supported.
 */
export const CHANNEL_TYPES = [
  {
    value: 'jira',
    category: 'tracker',
    descriptionKey: 'relay.typeJiraDesc',
    actions: [
      { key: 'new', support: 'full' },
      { key: 'link', support: 'full' },
      { key: 'update', support: 'full' }
    ]
  },
  {
    value: 'github_issue',
    category: 'tracker',
    descriptionKey: 'relay.typeGitHubDesc',
    actions: [
      { key: 'new', support: 'full' },
      { key: 'link', support: 'full' },
      { key: 'update', support: 'full' }
    ]
  },
  {
    value: 'feishu_bitable',
    category: 'table',
    descriptionKey: 'relay.typeFeishuDesc',
    actions: [
      { key: 'new', support: 'full' },
      { key: 'link', support: 'partial' },
      { key: 'update', support: 'full' }
    ]
  }
]
