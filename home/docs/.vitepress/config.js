import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'AImyChats',
  description: 'AI-Powered Conversation Management Platform',

  locales: {
    root: {
      label: 'English',
      lang: 'en-US',
      title: 'AImyChats',
      description: 'AI-Powered Conversation Hub',
      themeConfig: {
        nav: [
          { text: 'Home', link: '/' },
          { text: 'Features', link: '/#features' },
          { text: 'Pricing', link: '/#pricing' },
          { text: 'Self-Hosting', link: '/en/self-hosting/deployment/overview' },
          { text: 'User Guide', link: '/en/guide/console' },
          { text: 'GitHub', link: 'https://github.com/cloud2ai/devify' }
        ],
        sidebar: {
          '/en/guide/': [
            {
              text: 'User Guide',
              items: [
                { text: 'Using the Console', link: '/en/guide/console' },
                { text: 'TODOs & Smart Delivery', link: '/en/guide/delivery' },
                { text: 'Account, Settings & Billing', link: '/en/guide/account' }
              ]
            },
            {
              text: 'More',
              items: [
                { text: 'Getting Started', link: '/en/guide/getting-started' },
                { text: 'Integrations', link: '/en/guide/integrations' }
              ]
            }
          ],
          '/en/self-hosting/': [
            {
              text: 'Deployment',
              items: [
                { text: 'Overview', link: '/en/self-hosting/deployment/overview' },
                { text: 'Development', link: '/en/self-hosting/deployment/development' },
                { text: 'Production', link: '/en/self-hosting/deployment/production' },
                { text: 'Inbound Email (Haraka)', link: '/en/self-hosting/deployment/haraka' },
                { text: 'First Run', link: '/en/self-hosting/deployment/first-run' },
                { text: 'Troubleshooting', link: '/en/self-hosting/deployment/troubleshooting' }
              ]
            },
            {
              text: 'Configuration',
              items: [
                { text: 'Environment Variables', link: '/en/self-hosting/configuration/environment' },
                { text: 'Database', link: '/en/self-hosting/configuration/database' },
                { text: 'LLM Providers', link: '/en/self-hosting/configuration/llm-providers' },
                { text: 'Email & Notifications', link: '/en/self-hosting/configuration/email-notifications' },
                { text: 'OAuth Login', link: '/en/self-hosting/configuration/oauth' },
                { text: 'App Settings & Model Binding', link: '/en/self-hosting/configuration/app-settings' }
              ]
            }
          ]
        },
        footer: {
          message: '',
          copyright: ''
        }
      }
    },
    zh: {
      label: '中文',
      lang: 'zh-CN',
      title: 'AImyChats',
      description: '微信聊天备份 + AI 智能助手',
      themeConfig: {
        nav: [
          { text: '首页', link: '/zh/' },
          { text: '功能', link: '/zh/#features' },
          { text: '价格', link: '/zh/#pricing' },
          { text: '私有化部署', link: '/zh/self-hosting/deployment/overview' },
          { text: '使用帮助', link: '/zh/guide/console' },
          { text: 'GitHub', link: 'https://github.com/cloud2ai/devify' }
        ],
        sidebar: {
          '/zh/guide/': [
            {
              text: '使用手册',
              items: [
                { text: '控制台使用', link: '/zh/guide/console' },
                { text: '待办与智能投递', link: '/zh/guide/delivery' },
                { text: '账户、设置与计费', link: '/zh/guide/account' }
              ]
            },
            {
              text: '更多',
              items: [
                { text: '微信备份', link: '/zh/guide/wechat-backup' },
                { text: '功能说明', link: '/zh/guide/features' }
              ]
            }
          ],
          '/zh/self-hosting/': [
            {
              text: '部署',
              items: [
                { text: '概览', link: '/zh/self-hosting/deployment/overview' },
                { text: '开发环境', link: '/zh/self-hosting/deployment/development' },
                { text: '生产环境', link: '/zh/self-hosting/deployment/production' },
                { text: '入站邮件 (Haraka)', link: '/zh/self-hosting/deployment/haraka' },
                { text: '首次运行', link: '/zh/self-hosting/deployment/first-run' },
                { text: '故障排查', link: '/zh/self-hosting/deployment/troubleshooting' }
              ]
            },
            {
              text: '配置',
              items: [
                { text: '环境变量', link: '/zh/self-hosting/configuration/environment' },
                { text: '数据库', link: '/zh/self-hosting/configuration/database' },
                { text: '模型提供商', link: '/zh/self-hosting/configuration/llm-providers' },
                { text: '邮件与通知', link: '/zh/self-hosting/configuration/email-notifications' },
                { text: 'OAuth 登录', link: '/zh/self-hosting/configuration/oauth' },
                { text: '应用设置与模型绑定', link: '/zh/self-hosting/configuration/app-settings' }
              ]
            }
          ]
        },
        footer: {
          message: '',
          copyright: ''
        }
      }
    }
  },

  themeConfig: {
    logo: '/android-chrome-192x192.png',
    siteTitle: 'AImyChats',
    socialLinks: []
  },

  appearance: false,

  head: [
    ['link', { rel: 'icon', href: '/favicon.ico' }],
    ['meta', { name: 'viewport', content: 'width=device-width, initial-scale=1.0' }],
    ['script', { async: '', src: 'https://www.googletagmanager.com/gtag/js?id=G-TJWJHQH4M9' }],
    ['script', {}, `
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-TJWJHQH4M9');
    `]
  ],

  vite: {
    server: {
      host: '0.0.0.0',
      strictPort: false,
    },
    resolve: {
      alias: {
        '@': '/docs/.vitepress/theme'
      }
    }
  }
})
