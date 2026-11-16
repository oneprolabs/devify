<template>
  <AdminLayout>
    <div class="p-6 w-full min-w-0">
      <header class="mb-5">
        <h1 class="text-lg font-semibold text-gray-900">问题反馈</h1>
        <p class="mt-1 text-sm text-gray-500">
          查看客户端问题、诊断材料与处理进度。
        </p>
      </header>
      <div class="flex flex-wrap gap-3 items-center mb-4">
        <label class="text-sm"
          >状态
          <select
            v-model="status"
            class="border border-gray-300 rounded px-3 py-2"
            @change="load(1)"
          >
            <option value="">全部</option>
            <option v-for="(label, key) in statuses" :key="key" :value="key">
              {{ label }}
            </option>
          </select></label
        >
        <button
          type="button"
          :disabled="loading"
          class="border border-gray-300 rounded px-3 py-2 text-sm"
          @click="load(page)"
        >
          刷新</button
        ><span class="text-sm text-gray-500">共 {{ total }} 条反馈</span>
      </div>
      <p v-if="error" role="alert" class="text-red-600 text-sm mb-4">
        {{ error }}
      </p>
      <div class="grid gap-5" :class="selected ? 'xl:grid-cols-2' : ''">
        <section
          class="border border-gray-200 rounded-lg bg-white overflow-hidden min-w-0"
          aria-label="反馈列表"
        >
          <p v-if="loading" role="status" class="p-8 text-center text-gray-500">
            正在读取反馈…
          </p>
          <p v-else-if="!reports.length" class="p-10 text-center text-gray-500">
            当前没有反馈。
          </p>
          <template v-else
            ><button
              v-for="report in reports"
              :key="report.id"
              type="button"
              class="block w-full text-left p-4 border-b border-gray-100 hover:bg-gray-50"
              :class="selected?.id === report.id ? 'bg-gray-50' : ''"
              @click="selected = report"
            >
              <span class="flex justify-between gap-4"
                ><strong class="text-sm text-gray-900">{{
                  categories[report.category] || report.category
                }}</strong
                ><span
                  class="text-xs"
                  :class="
                    report.status === 'resolved'
                      ? 'text-green-700'
                      : 'text-gray-500'
                  "
                  >{{ statuses[report.status] }}</span
                ></span
              ><span
                class="block text-sm mt-2 text-gray-700 line-clamp-2 break-words"
                >{{ report.description }}</span
              ><span class="block text-xs text-gray-500 mt-2"
                >{{ report.submitted_by }} ·
                {{ new Date(report.created_at).toLocaleString() }}</span
              >
            </button></template
          >
          <footer class="flex items-center justify-between p-4 text-sm">
            <button
              type="button"
              :disabled="loading || page === 1"
              @click="load(page - 1)"
            >
              上一页</button
            ><span>第 {{ page }} 页</span
            ><button
              type="button"
              :disabled="loading || !next"
              @click="load(page + 1)"
            >
              下一页
            </button>
          </footer>
        </section>
        <FeedbackDetail
          v-if="selected"
          :key="selected.id"
          :report="selected"
          @close="selected = null"
          @updated="update"
        />
      </div>
    </div>
  </AdminLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import FeedbackDetail from './FeedbackDetail.vue'
import { feedbackApi } from '@/admin/api/feedback'
import { extractErrorMessage } from '@/utils/api'

const statuses = {
  received: '已收到',
  processing: '处理中',
  needs_info: '待补充',
  resolved: '已解决'
}
const categories = {
  wechat: '连接微信',
  backup: '聊天备份',
  upload: '上传分析',
  login: '登录',
  interface: '界面异常',
  other: '其他问题'
}
const reports = ref([]),
  selected = ref(null),
  status = ref(''),
  total = ref(0),
  page = ref(1),
  next = ref(false),
  loading = ref(false),
  error = ref('')
let sequence = 0
async function load(number) {
  const request = ++sequence
  loading.value = true
  error.value = ''
  try {
    const data = await feedbackApi.list({ page: number, status: status.value })
    if (request !== sequence) return
    reports.value = data.results
    total.value = data.count
    page.value = number
    next.value = !!data.next
  } catch (err) {
    if (request === sequence)
      error.value = extractErrorMessage(err, '读取反馈失败。')
  } finally {
    if (request === sequence) loading.value = false
  }
}
function update(report) {
  selected.value = report
  reports.value = reports.value.map((item) =>
    item.id === report.id ? report : item
  )
}
onMounted(() => load(1))
</script>
