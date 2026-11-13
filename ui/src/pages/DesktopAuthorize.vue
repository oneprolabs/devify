<template>
  <div class="desktop-authorize">
    <p v-if="loading">正在准备 Wechatify 登录…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/index'

const route = useRoute()
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const response = await api.get('/v1/auth/desktop/authorize', {
      params: {
        ...route.query,
        mode: 'browser'
      }
    })
    const data = response.data.data || response.data
    if (!data.redirect_url) throw new Error('授权响应缺少回调地址。')
    window.location.href = data.redirect_url
  } catch (requestError) {
    error.value =
      requestError.response?.data?.detail ||
      requestError.message ||
      '无法准备授权。'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.desktop-authorize {
  display: grid;
  min-height: 100vh;
  place-items: center;
  color: rgb(var(--c-tx2));
  font-size: 14px;
}
.desktop-authorize [role='alert'] {
  color: rgb(var(--c-bad));
}
</style>
