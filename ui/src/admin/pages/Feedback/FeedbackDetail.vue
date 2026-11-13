<template>
  <section
    class="rounded-lg border border-gray-200 bg-white p-5 min-w-0"
    aria-label="反馈详情"
  >
    <header class="flex items-center justify-between gap-4 mb-4">
      <h2 class="font-semibold text-gray-900">反馈详情</h2>
      <button
        type="button"
        class="text-sm text-gray-500"
        @click="$emit('close')"
      >
        关闭详情
      </button>
    </header>
    <p class="text-xs text-gray-500 break-all">
      {{ report.id }} · {{ report.submitted_by }}
    </p>
    <p class="whitespace-pre-wrap break-words my-4 text-sm">
      {{ report.description }}
    </p>
    <p v-if="report.contact" class="text-sm mb-4">
      联系方式：{{ report.contact }}
    </p>
    <div class="flex flex-wrap gap-2 mb-4">
      <button
        v-for="(item, index) in report.attachments"
        :key="item.id"
        type="button"
        class="px-3 py-2 rounded border border-gray-200 text-sm"
        :disabled="item.expired || downloading"
        @click="download(item)"
      >
        {{ item.expired ? '附件已过期' : `下载截图 ${index + 1}` }}
      </button>
    </div>
    <details class="text-sm mb-4">
      <summary class="cursor-pointer text-gray-600">环境与诊断信息</summary>
      <pre
        class="mt-2 p-3 bg-gray-50 rounded overflow-auto max-h-64 text-xs whitespace-pre-wrap break-all"
        >{{
          JSON.stringify(
            { context: report.context, diagnostics: report.diagnostics },
            null,
            2
          )
        }}</pre
      >
    </details>
    <form
      class="space-y-4 border-t border-gray-100 pt-4"
      @submit.prevent="save"
    >
      <label class="block text-sm"
        >处理状态<select
          v-model="form.status"
          class="mt-1 w-full border border-gray-300 rounded px-3 py-2"
        >
          <option value="received">已收到</option>
          <option value="processing">处理中</option>
          <option value="needs_info">待补充</option>
          <option value="resolved">已解决</option>
        </select></label
      >
      <label class="block text-sm"
        >处理人用户 ID（选填）<input
          v-model="assignee"
          type="number"
          min="1"
          class="mt-1 w-full border border-gray-300 rounded px-3 py-2"
          placeholder="管理员用户 ID"
      /></label>
      <label class="block text-sm"
        >回复用户<textarea
          v-model="form.reply"
          rows="4"
          maxlength="5000"
          class="mt-1 w-full border border-gray-300 rounded px-3 py-2"
          placeholder="说明处理进展或需要补充的信息"
        />
      </label>
      <label class="block text-sm"
        >修复版本<input
          v-model="form.fix_version"
          maxlength="64"
          class="mt-1 w-full border border-gray-300 rounded px-3 py-2"
          placeholder="例如 0.1.1"
      /></label>
      <p v-if="error" role="alert" class="text-sm text-red-600">{{ error }}</p>
      <p v-if="saved" role="status" class="text-sm text-green-700">
        处理结果已保存，用户可在客户端查看。
      </p>
      <button
        type="submit"
        :disabled="busy"
        class="px-4 py-2 rounded bg-primary-600 text-white text-sm disabled:opacity-50"
      >
        {{ busy ? '保存中…' : '保存处理结果' }}
      </button>
    </form>
  </section>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { feedbackApi } from '@/admin/api/feedback'
import { extractErrorMessage } from '@/utils/api'

const props = defineProps({ report: { type: Object, required: true } })
const emit = defineEmits(['close', 'updated'])
const form = reactive({ status: '', reply: '', fix_version: '' })
const assignee = ref('')
const busy = ref(false)
const downloading = ref(false)
const saved = ref(false)
const error = ref('')
watch(
  () => props.report,
  (report) => {
    Object.assign(form, {
      status: report.status,
      reply: report.reply,
      fix_version: report.fix_version
    })
    assignee.value = report.assigned_to || ''
    error.value = ''
    saved.value = false
  },
  { immediate: true }
)
async function save() {
  busy.value = true
  error.value = ''
  saved.value = false
  try {
    const report = await feedbackApi.update(props.report.id, {
      ...form,
      assigned_to: assignee.value ? Number(assignee.value) : null
    })
    emit('updated', report)
    saved.value = true
  } catch (err) {
    error.value = extractErrorMessage(err, '保存失败，请重试。')
  } finally {
    busy.value = false
  }
}
async function download(item) {
  downloading.value = true
  error.value = ''
  try {
    await feedbackApi.download(item)
  } catch (err) {
    error.value = extractErrorMessage(err, '下载失败，请重试。')
  } finally {
    downloading.value = false
  }
}
</script>
