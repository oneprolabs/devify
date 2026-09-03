<template>
  <div class="space-y-5">
    <!-- The type is what this channel *is*: changing it would invalidate the
         connection, the strategies and every field mapping, so it reads as an
         identity line with a deliberate way back to the gallery. -->
    <div
      class="flex items-center gap-3 rounded-lg border border-line bg-panel-sub px-4 py-3"
    >
      <span
        class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-chip font-mono text-[11px] font-semibold text-ink-2"
      >
        {{ TYPE_INITIALS[editorForm.target_type] || '··' }}
      </span>
      <span class="flex flex-col gap-px">
        <span class="text-[13px] font-semibold text-ink">
          {{
            t(TYPE_LABEL_KEYS[editorForm.target_type] || 'relay.targetFeishu')
          }}
        </span>
        <span class="text-[11.5px] text-ink-3">
          {{ t('relay.channelTypeHelp') }}
        </span>
      </span>
      <button
        type="button"
        class="ml-auto text-[11.5px] text-accent hover:underline"
        @click="editorForm.target_type = ''"
      >
        {{ t('relay.changeType') }}
      </button>
    </div>

    <div class="flex flex-col gap-3 md:flex-row md:gap-7">
      <div class="md:w-44 md:flex-none">
        <label class="block text-sm font-medium text-ink-2 mb-1">
          {{ t('relay.name') }}
        </label>
        <p class="text-xs text-ink-3">
          {{ t('relay.channelNameHelp') }}
        </p>
      </div>
      <div class="min-w-0 md:max-w-[640px] md:flex-1">
        <input v-model="editorForm.name" class="input" />
      </div>
    </div>

    <div class="grid grid-cols-1 gap-2 md:grid-cols-3 md:gap-4 md:items-center">
      <div class="md:w-44 md:flex-none">
        <label class="block text-sm font-medium text-ink-2 mb-1">
          {{ t('relay.enabled') }}
        </label>
        <p class="text-xs text-ink-3">
          {{ t('relay.channelEnabledHelp') }}
        </p>
      </div>
      <div class="min-w-0 md:max-w-[640px] md:flex-1">
        <label class="flex items-center gap-2 text-sm text-ink-2">
          <input
            v-model="editorForm.enabled"
            type="checkbox"
            class="rounded border-line"
          />
          {{ editorForm.enabled ? t('common.yes') : t('common.no') }}
        </label>
      </div>
    </div>

    <div class="flex flex-col gap-3 md:flex-row md:gap-7">
      <div class="md:w-44 md:flex-none">
        <label class="block text-sm font-medium text-ink-2 mb-1">
          {{ t('relay.language') }}
        </label>
        <p class="text-xs text-ink-3">
          {{ t('relay.languageHelp') }}
        </p>
      </div>
      <div class="min-w-0 md:max-w-[640px] md:flex-1">
        <select v-model="editorForm.language" class="input">
          <option value="Chinese">
            {{ t('relay.languageChinese') }}
          </option>
          <option value="English">
            {{ t('relay.languageEnglish') }}
          </option>
        </select>
      </div>
    </div>

    <div class="rounded-lg border border-line bg-app-sub p-4 space-y-4">
      <div>
        <h4 class="text-sm font-semibold text-ink">
          {{ t('relay.strategiesTitle') }}
        </h4>
        <p class="mt-1 text-xs text-ink-3">
          {{ t('relay.strategiesHelp') }}
        </p>
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div>
          <label class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('settings.autoMergeStrategy') }}
          </label>
          <select
            v-model="editorForm.strategies.auto_merge_strategy"
            class="input"
          >
            <option value="new">
              {{ t('settings.autoMergeStrategyNew') }}
            </option>
            <option value="update">
              {{ t('settings.autoMergeStrategyUpdate') }}
            </option>
          </select>
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('settings.manualMergeStrategy') }}
          </label>
          <select
            v-model="editorForm.strategies.manual_merge_strategy"
            class="input"
          >
            <option value="linked">
              {{ t('settings.manualMergeStrategyLinked') }}
            </option>
            <option value="unlinked">
              {{ t('settings.manualMergeStrategyUnlinked') }}
            </option>
          </select>
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('settings.retryIssueStrategy') }}
          </label>
          <select
            v-model="editorForm.strategies.retry_issue_strategy"
            class="input"
          >
            <option value="new">
              {{ t('settings.retryIssueStrategyNew') }}
            </option>
            <option value="update">
              {{ t('settings.retryIssueStrategyUpdate') }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div
      v-if="editorForm.target_type === 'feishu_bitable'"
      class="rounded-lg border border-line bg-app-sub p-4 space-y-4"
    >
      <div>
        <h4 class="text-sm font-semibold text-ink">
          {{ t('relay.feishuConfigTitle') }}
        </h4>
        <p class="mt-1 text-xs text-ink-3">
          {{ t('settings.feishuConfigDesc1') }}
        </p>
        <p class="mt-1 text-xs text-ink-3">
          {{ t('settings.feishuConfigDesc2') }}
        </p>
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BaseInput
          v-model="editorForm.feishuConfig.app_id"
          :label="t('settings.feishuAppId')"
          :placeholder="t('settings.feishuAppIdPlaceholder')"
        />
        <div>
          <label class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('settings.feishuAppSecret') }}
          </label>
          <div class="relative">
            <input
              v-model="editorForm.feishuConfig.app_secret"
              :type="showFeishuAppSecret ? 'text' : 'password'"
              class="input pr-10"
              :placeholder="t('settings.feishuAppSecretPlaceholder')"
              autocomplete="new-password"
            />
            <button
              type="button"
              class="absolute inset-y-0 right-0 flex items-center pr-3 text-ink-4 transition hover:text-ink-2"
              :aria-label="
                showFeishuAppSecret ? t('common.hide') : t('common.show')
              "
              :title="showFeishuAppSecret ? t('common.hide') : t('common.show')"
              @click="showFeishuAppSecret = !showFeishuAppSecret"
            >
              <svg
                v-if="!showFeishuAppSecret"
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M3.98 8.223A10.48 10.48 0 0 0 1.934 12c1.73 4.943 6.402 8.5 12.066 8.5 1.618 0 3.159-.3 4.578-.845m3.42-2.113A10.44 10.44 0 0 0 22.065 12C20.335 7.057 15.663 3.5 10 3.5c-1.618 0-3.159.3-4.578.845m3.42 2.113A5 5 0 1 1 18 12a5 5 0 0 1-9.158-2.579Z"
                />
              </svg>
              <svg
                v-else
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M2.25 3.75 21 22.5m-2.255-2.255A10.47 10.47 0 0 1 12 20.5c-5.664 0-10.336-3.557-12.066-8.5a10.53 10.53 0 0 1 3.034-4.223m3.079-2.113A10.42 10.42 0 0 1 12 3.5c5.664 0 10.336 3.557 12.066 8.5a10.49 10.49 0 0 1-4.143 5.277M9.88 9.88A3 3 0 0 0 14.12 14.12"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div class="space-y-1">
          <label class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('settings.feishuAppTokenType') }}
          </label>
          <select
            v-model="editorForm.feishuConfig.app_token_type"
            class="input"
          >
            <option value="bitable">
              {{ t('settings.feishuAppTokenTypeBitable') }}
            </option>
            <option value="wiki">
              {{ t('settings.feishuAppTokenTypeWiki') }}
            </option>
          </select>
          <p class="text-xs text-ink-3">
            {{ t('settings.feishuAppTokenTypeHelp') }}
          </p>
        </div>

        <BaseInput
          v-model="editorForm.feishuConfig.app_token"
          :label="t('settings.feishuAppToken')"
          :placeholder="t('settings.feishuAppTokenPlaceholder')"
          :help="t('settings.feishuAppTokenHelp')"
        />
      </div>

      <BaseInput
        v-model="editorForm.feishuConfig.table_name"
        :label="t('settings.feishuTableName')"
        :placeholder="t('settings.feishuTableNamePlaceholder')"
        :help="t('settings.feishuTableNameHelp')"
      />

      <BaseInput
        v-model="editorForm.feishuConfig.summary_prefix"
        :label="t('relay.feishuSummaryPrefix')"
        :placeholder="t('relay.feishuSummaryPrefixPlaceholder')"
        :help="t('relay.feishuSummaryPrefixHelp')"
      />

      <div class="rounded-lg border border-line bg-app-sub p-4 space-y-4">
        <div class="space-y-2">
          <div>
            <h5 class="text-sm font-semibold text-ink">
              {{ t('settings.feishuFieldMappings') }}
            </h5>
            <p class="mt-1 text-xs text-ink-3">
              {{ t('settings.feishuFieldMappingsHelp') }}
            </p>
            <p class="mt-1 text-xs text-ink-3">
              {{ t('settings.feishuFieldMappingsDetail') }}
            </p>
          </div>
        </div>

        <div class="space-y-3">
          <div
            v-for="(mapping, index) in editorForm.fieldMappingRows"
            :key="`mapping-${index}`"
            class="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_1fr_auto]"
          >
            <BaseInput
              v-model="mapping.source"
              :label="t('settings.feishuFieldMappingSource')"
              :placeholder="t('settings.feishuFieldMappingSourcePlaceholder')"
            />
            <BaseInput
              v-model="mapping.target"
              :label="t('settings.feishuFieldMappingTarget')"
              :placeholder="t('settings.feishuFieldMappingTargetPlaceholder')"
            />
            <div class="flex items-end">
              <BaseButton
                variant="secondary"
                size="sm"
                class="w-full lg:w-auto"
                @click="
                  index === 0
                    ? addFieldMappingRow()
                    : removeFieldMappingRow(index)
                "
                :aria-label="
                  index === 0
                    ? t('relay.addMappingRow')
                    : t('relay.removeMappingRow')
                "
              >
                <svg
                  v-if="index === 0"
                  class="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 5v14m7-7H5"
                  />
                </svg>
                <svg
                  v-else
                  class="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M5 12h14"
                  />
                </svg>
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <div class="rounded-lg border border-line bg-app-sub p-4 space-y-4">
        <BaseInput
          v-model="editorForm.feishuConfig.attachment_field_name"
          :label="t('settings.feishuAttachmentFieldName')"
          :placeholder="t('settings.feishuAttachmentFieldNamePlaceholder')"
          :help="t('settings.feishuAttachmentMappingHelp')"
        />
      </div>
    </div>

    <div
      v-else-if="editorForm.target_type === 'jira'"
      class="rounded-lg border border-line bg-app-sub p-4 space-y-4"
    >
      <div>
        <h4 class="text-sm font-semibold text-ink">
          {{ t('relay.jiraConfigTitle') }}
        </h4>
        <p class="mt-1 text-xs text-ink-3">
          {{ t('relay.jiraConfigHelp') }}
        </p>
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BaseInput
          v-model="editorForm.jiraConfig.url"
          :label="t('relay.jiraUrl')"
          :placeholder="t('relay.jiraUrlPlaceholder')"
        />
        <BaseInput
          v-model="editorForm.jiraConfig.username"
          :label="t('relay.jiraUsername')"
          :placeholder="t('relay.jiraUsernamePlaceholder')"
        />
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BaseInput
          v-model="editorForm.jiraConfig.api_token"
          :label="t('relay.jiraApiToken')"
          :placeholder="t('relay.jiraApiTokenPlaceholder')"
        />
        <BaseInput
          v-model="editorForm.jiraConfig.project_key"
          :label="t('relay.jiraProjectKey')"
          :placeholder="t('relay.jiraProjectKeyPlaceholder')"
        />
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BaseInput
          v-model="editorForm.jiraConfig.issue_type_default"
          :label="t('relay.jiraIssueTypeDefault')"
          :placeholder="t('relay.jiraIssueTypeDefaultPlaceholder')"
        />
        <BaseInput
          v-model="editorForm.jiraConfig.priority_default"
          :label="t('relay.jiraPriorityDefault')"
          :placeholder="t('relay.jiraPriorityDefaultPlaceholder')"
        />
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BaseInput
          v-model="editorForm.jiraConfig.summary_prefix"
          :label="t('relay.jiraSummaryPrefix')"
          :placeholder="t('relay.jiraSummaryPrefixPlaceholder')"
        />

        <div class="space-y-3">
          <label class="block text-sm font-medium text-ink-2">
            {{ t('relay.jiraSummaryOptions') }}
          </label>
          <label class="flex items-center gap-2 text-sm text-ink-2">
            <input
              v-model="editorForm.jiraConfig.add_timestamp"
              type="checkbox"
              class="rounded border-line text-accent focus:ring-accent"
            />
            {{ t('relay.jiraAddTimestamp') }}
          </label>
        </div>
      </div>

      <BaseInput
        v-model="editorForm.jiraConfig.description_field"
        :label="t('settings.jiraDescriptionField')"
        :placeholder="t('settings.jiraDescriptionFieldPlaceholder')"
        :help="t('settings.jiraDescriptionFieldHelp')"
      />

      <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <label class="flex items-center gap-2 text-sm text-ink-2">
          <input
            v-model="editorForm.jiraConfig.convert_to_jira_wiki"
            type="checkbox"
            class="rounded border-line text-accent focus:ring-accent"
          />
          {{ t('relay.jiraConvertToWiki') }}
        </label>
        <label class="flex items-center gap-2 text-sm text-ink-2">
          <input
            v-model="editorForm.jiraConfig.assignee_use_llm"
            type="checkbox"
            class="rounded border-line text-accent focus:ring-accent"
          />
          {{ t('relay.jiraAssigneeUseLlm') }}
        </label>
      </div>

      <div class="rounded-lg border border-line bg-app-sub p-4 space-y-4">
        <div>
          <h4 class="text-sm font-semibold text-ink">
            {{ t('settings.jiraAssigneeSectionTitle') }}
          </h4>
          <p class="mt-1 text-xs text-ink-3">
            {{ t('settings.jiraAssigneeSectionDesc') }}
          </p>
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BaseInput
            v-model="editorForm.jiraConfig.assignee_default"
            :label="t('settings.jiraAssigneeDefault')"
            :placeholder="t('settings.jiraAssigneeDefaultPlaceholder')"
            :help="t('settings.jiraAssigneeDefaultHelp')"
          />
          <div>
            <label class="mb-1 block text-sm font-medium text-ink-2">
              {{ t('settings.jiraAssigneeAllowValues') }}
            </label>
            <textarea
              v-model="editorForm.jiraConfig.assignee_allow_values_text"
              class="input min-h-[96px]"
              :placeholder="t('settings.jiraAssigneeAllowValuesPlaceholder')"
            />
            <p class="mt-1 text-xs text-ink-3">
              {{ t('settings.jiraAssigneeAllowValuesHelp') }}
            </p>
          </div>
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('settings.jiraAssigneePrompt') }}
          </label>
          <textarea
            v-model="editorForm.jiraConfig.assignee_prompt"
            class="input min-h-[96px]"
            :placeholder="t('settings.jiraAssigneePromptPlaceholder')"
          />
          <p class="mt-1 text-xs text-ink-3">
            {{ t('settings.jiraAssigneePromptHelp') }}
          </p>
        </div>
      </div>

      <div class="rounded-lg border border-line bg-app-sub p-4 space-y-4">
        <div>
          <h4 class="text-sm font-semibold text-ink">
            {{ t('settings.jiraComponentsSectionTitle') }}
          </h4>
          <p class="mt-1 text-xs text-ink-3">
            {{ t('settings.jiraComponentsSectionDesc') }}
          </p>
        </div>

        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <label class="flex items-center gap-2 text-sm text-ink-2">
            <input
              v-model="editorForm.jiraConfig.components_use_llm"
              type="checkbox"
              class="rounded border-line text-accent focus:ring-accent"
            />
            {{ t('settings.jiraComponentsUseLlm') }}
          </label>
          <label class="flex items-center gap-2 text-sm text-ink-2">
            <input
              v-model="editorForm.jiraConfig.components_fetch_from_api"
              type="checkbox"
              class="rounded border-line text-accent focus:ring-accent"
            />
            {{ t('settings.jiraComponentsFetchFromApi') }}
          </label>
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <label class="mb-1 block text-sm font-medium text-ink-2">
              {{ t('settings.jiraComponentsDefault') }}
            </label>
            <textarea
              v-model="editorForm.jiraConfig.components_default_text"
              class="input min-h-[96px]"
              :placeholder="t('settings.jiraComponentsDefaultPlaceholder')"
            />
            <p class="mt-1 text-xs text-ink-3">
              {{ t('settings.jiraComponentsDefaultHelp') }}
            </p>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-ink-2">
              {{ t('settings.jiraComponentsPrompt') }}
            </label>
            <textarea
              v-model="editorForm.jiraConfig.components_prompt"
              class="input min-h-[96px]"
              :placeholder="t('settings.jiraComponentsPromptPlaceholder')"
            />
            <p class="mt-1 text-xs text-ink-3">
              {{ t('settings.jiraComponentsPromptHelp') }}
            </p>
          </div>
        </div>
      </div>

      <div class="rounded-lg border border-line bg-app-sub p-4 space-y-4">
        <div>
          <h4 class="text-sm font-semibold text-ink">
            {{ t('settings.jiraEpicLinkSectionTitle') }}
          </h4>
          <p class="mt-1 text-xs text-ink-3">
            {{ t('settings.jiraEpicLinkSectionDesc') }}
          </p>
        </div>

        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <label class="flex items-center gap-2 text-sm text-ink-2">
            <input
              v-model="editorForm.jiraConfig.epic_link_fetch_from_api"
              type="checkbox"
              class="rounded border-line text-accent focus:ring-accent"
            />
            {{ t('settings.jiraEpicLinkFetchFromApi') }}
          </label>
          <label class="flex items-center gap-2 text-sm text-ink-2">
            <input
              v-model="editorForm.jiraConfig.epic_link_use_llm"
              type="checkbox"
              class="rounded border-line text-accent focus:ring-accent"
            />
            {{ t('settings.jiraEpicLinkUseLlm') }}
          </label>
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BaseInput
            v-model="editorForm.jiraConfig.epic_link_default"
            :label="t('settings.jiraEpicLinkDefault')"
            :placeholder="t('settings.jiraEpicLinkDefaultPlaceholder')"
            :help="t('settings.jiraEpicLinkDefaultHelp')"
          />
          <BaseInput
            v-model="editorForm.jiraConfig.epic_link_jql_filter"
            :label="t('settings.jiraEpicLinkJqlFilter')"
            :placeholder="t('settings.jiraEpicLinkJqlFilterPlaceholder')"
            :help="t('settings.jiraEpicLinkJqlFilterHelp')"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-ink-2">
            {{ t('settings.jiraEpicLinkPrompt') }}
          </label>
          <textarea
            v-model="editorForm.jiraConfig.epic_link_prompt"
            class="input min-h-[96px]"
            :placeholder="t('settings.jiraEpicLinkPromptPlaceholder')"
          />
          <p class="mt-1 text-xs text-ink-3">
            {{ t('settings.jiraEpicLinkPromptHelp') }}
          </p>
        </div>
      </div>
    </div>

    <GitHubIssueConfig
      v-else-if="editorForm.target_type === 'github_issue'"
      v-model="editorForm.githubConfig"
    />
  </div>

  <p v-if="editorError" class="text-sm text-bad">
    {{ editorError }}
  </p>
  <p v-if="editorSuccess && editorTestPassed" class="text-sm text-ok">
    {{ editorSuccess }}
  </p>

  <div class="flex justify-end pt-2">
    <div class="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
      <BaseButton
        variant="secondary"
        class="w-full sm:w-auto"
        :disabled="saving"
        @click="cancelEditor"
      >
        {{ t('common.cancel') }}
      </BaseButton>
      <BaseButton
        variant="secondary"
        class="w-full sm:w-auto"
        :loading="testing"
        :disabled="saving"
        @click="runEditorTest"
      >
        {{ t('relay.runTest') }}
      </BaseButton>
      <BaseButton
        class="w-full sm:w-auto"
        :loading="saving"
        :disabled="saving || testing || !editorCanSave"
        @click="saveEditor"
      >
        {{ t('relay.saveTargets') }}
      </BaseButton>
    </div>
  </div>
  <p v-if="!editorCanSave" class="text-xs text-warn">
    {{ t('relay.saveAfterTestHint') }}
  </p>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import GitHubIssueConfig from '@/components/relay/GitHubIssueConfig.vue'
import { TYPE_INITIALS, TYPE_LABEL_KEYS } from './channelTypes'

const props = defineProps({
  // The page owns `useRelayEditor`; this component only draws it.
  editor: { type: Object, required: true }
})

const { t } = useI18n()

const {
  saving,
  testing,
  showFeishuAppSecret,
  editorError,
  editorSuccess,
  editorForm,
  editorTestPassed,
  editorCanSave,
  addFieldMappingRow,
  removeFieldMappingRow,
  cancelEditor,
  saveEditor,
  runEditorTest
} = props.editor
</script>
