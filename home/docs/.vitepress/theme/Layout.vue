<template>
  <Layout>
    <template #nav-bar-content-after>
      <LanguageSwitcher />
    </template>
    <template #not-found>
      <NotFound />
    </template>
  </Layout>
</template>

<script setup>
import DefaultTheme from 'vitepress/theme'
import LanguageSwitcher from './components/LanguageSwitcher.vue'
import NotFound from './NotFound.vue'

const { Layout } = DefaultTheme
</script>
