---
layout: page
---

<script setup>
import Hero from '../.vitepress/theme/components/Hero.vue'
import Features from '../.vitepress/theme/components/Features.vue'
import HowItWorks from '../.vitepress/theme/components/HowItWorks.vue'
import WeChatGuide from '../.vitepress/theme/components/WeChatGuide.vue'
import UseCases from '../.vitepress/theme/components/UseCases.vue'
import OpenSourceBanner from '../.vitepress/theme/components/OpenSourceBanner.vue'
import Pricing from '../.vitepress/theme/components/Pricing.vue'
import ContactSection from '../.vitepress/theme/components/ContactSection.vue'
import Footer from '../.vitepress/theme/components/Footer.vue'

const heroData = {
  badge: '微信记录永不丢失 · AI 智能整理 · 秒速找回',
  githubUrl: 'https://github.com/cloud2ai/devify',
  title: '微信聊天记录<br>再也不会消失了',
  subtitle: '图片 30 天过期？换手机记录全没？一封转发邮件，AI 自动归档整理，永久保存，什么时候找都能找到。',
  points: [
    {
      icon: 'unified',
      text: '微信、邮件、WhatsApp 聊天记录统一归档'
    },
    {
      icon: 'ai',
      text: 'AI 识别截图文字、表格、图片内容'
    },
    {
      icon: 'search',
      text: '三年前的消息，几个字就能找到'
    },
    {
      icon: 'process',
      text: '转发 → 自动处理 → 永久保存'
    }
  ],
  primaryButtonText: '免费开始使用',
  primaryButtonLink: 'https://app.aimychats.com/register',
  secondaryButtonText: '查看功能介绍',
  secondaryButtonLink: '/zh/#features',
  carouselSlides: [
    {
      image: '/images/wechat-pain-zh.png',
      alt: '微信图片过期示意图',
      title: '你是否也有这个烦恼？',
      description: '微信图片 30 天后在电脑端消失，换手机聊天记录丢失，重要信息再也找不回来',
      highlights: ['图片过期', '记录丢失']
    },
    {
      image: '/images/dashboard-list-zh.png',
      alt: 'AImyChats 产品截图 - 聊天记录列表',
      title: '所有聊天记录，一个地方管起来',
      description: '微信、邮件、WhatsApp 全部汇聚到同一个界面，永久保存，智能搜索随时可用',
      highlights: ['统一管理', '秒速查找']
    },
    {
      image: '/images/ai-analysis-feature.png',
      alt: 'AI 智能分析示意图',
      title: 'AI 自动提炼关键信息',
      description: '每条聊天记录自动生成摘要、提取待办、识别图片内容，不再需要手动翻阅',
      highlights: ['自动摘要', '图文理解']
    }
  ],
  imageSrc: '/images/dashboard-list-zh.png',
  imageAlt: 'AImyChats 产品截图 - 列表页面',
  features: []
}

const howItWorksData = {
  title: '三步搞定，一分钟上手',
  subtitle: '不需要装插件，不需要授权微信，转发就能用',
  steps: [
    {
      icon: 'email',
      title: '转发聊天记录到专属邮箱',
      description: '在微信里选择「更多」→「通过邮件发送」，或者截图后直接发邮件。发到您的专属 AI 邮箱，系统自动接收。'
    },
    {
      icon: 'ai',
      title: 'AI 自动识别与分析',
      description: 'AI 自动提取关键信息、生成摘要、读懂图片内容，帮您识别重要待办和决策点，省去手动整理的时间。'
    },
    {
      icon: 'dashboard',
      title: '永久存档，随时搜索',
      description: '所有记录安全保存在云端，支持全文检索。换手机、清缓存都不影响。三年前的沟通细节，几秒就能找到。'
    }
  ]
}

const featuresData = {
  title: '解决微信用户最头疼的四个问题',
  subtitle: '不只是备份，是真正让信息变得可用',
  features: [
    {
      icon: 'backup',
      title: '图片永不过期，记录永不丢失',
      description: '微信图片 30 天后在电脑端消失，换手机聊天记录经常找不回来。AImyChats 让所有内容永久保存在云端，图片、文件、截图一个都不少。'
    },
    {
      icon: 'search',
      title: '找一条消息只需要几个字',
      description: '不用再一条条往上翻，不用记得是哪天说的。输入关键词，跨平台、跨时间、跨联系人，瞬间定位到那句话。'
    },
    {
      icon: 'image',
      title: '截图里的内容也能被 AI 读懂',
      description: '客户发来的报价截图、合同条款、设计稿、数据图表——AI 全部能识别和理解，让截图里的信息真正变得可搜索、可分析。'
    },
    {
      icon: 'backup',
      title: '微信、邮件、WhatsApp 一站管理',
      description: '不同客户用不同平台沟通？AImyChats 把所有渠道的记录统一归档，不再需要在多个 App 间来回切换找信息。'
    }
  ]
}

const useCasesData = {
  title: '哪些人最需要 AImyChats？',
  subtitle: '只要你有重要的微信沟通需要留存，这个工具就是为你准备的',
  useCases: [
    {
      icon: 'sales',
      role: '销售 / 客户经理',
      subtitle: '客户说过的每句话都有据可查',
      description: '客户在微信里谈的价格、需求、承诺，AI 自动整理成结构化记录，追责有凭据，复盘有数据。',
      benefits: [
        '客户沟通全程自动归档',
        '需求变更有据可查',
        '截图合同条款自动识别',
        '秒级搜索任意历史沟通'
      ]
    },
    {
      icon: 'team',
      role: '项目经理',
      subtitle: '群聊里的决策不再石沉大海',
      description: '项目群消息多、变更频繁、容易漏信息。AI 自动提炼每次讨论的关键决策、待办事项、责任人。',
      benefits: [
        '群聊讨论自动结构化整理',
        '需求变更历史可追溯',
        '待办事项自动提取',
        '多个项目群统一管理'
      ]
    },
    {
      icon: 'lawyer',
      role: '律师 / 顾问',
      subtitle: '每条沟通记录都是潜在证据',
      description: '客户咨询、合同谈判、案件沟通分散在微信和邮件里。AI 自动结构化整理，关键内容一搜即达。',
      benefits: [
        '多平台沟通统一归档',
        '图片证据内容 AI 识别',
        '关键条款和承诺自动提炼',
        '永久可查的历史记录'
      ]
    },
    {
      icon: 'team',
      role: '企业高管',
      subtitle: '跨平台沟通全局一览',
      description: '内部协作、客户沟通、合作谈判分散在微信、邮件多个渠道。AImyChats 让所有信息汇聚到一处，决策有迹可循。',
      benefits: [
        '跨渠道沟通统一管理',
        '重要决策永久留存',
        '多场景 AI 分析（项目 / 客户 / 内部）',
        '快速追溯任意决策背景'
      ]
    },
    {
      icon: 'doctor',
      role: '医生 / 咨询师',
      subtitle: '患者沟通完整留存，随时可查',
      description: '患者发来的检查报告截图、症状描述、复诊沟通——AI 自动归档识别，让每位患者的沟通历史完整清晰。',
      benefits: [
        '检验单 / 处方截图自动识别',
        '患者沟通永久保存',
        '关键症状和嘱咐自动提炼',
        '快速调取任意患者历史'
      ]
    },
    {
      icon: 'finance',
      role: '金融顾问',
      subtitle: '客户沟通责任边界清晰',
      description: '每次投资建议、客户确认、风险提示都有记录才安心。AI 帮你把分散在微信里的沟通整理成可追溯的档案。',
      benefits: [
        '投资沟通全程留档',
        '客户确认内容清晰记录',
        '截图识别还原客户意图',
        '合规风险可追溯'
      ]
    }
  ]
}

const pricingData = {
  title: '选择适合您的方案',
  subtitle: '个人免费试用，专业用户按需付费',
  featuredLabel: '最受欢迎',
  plans: [
    {
      name: '免费体验',
      description: ' ',
      price: '$0',
      period: '/ 月',
      buttonText: '免费开始',
      buttonLink: 'https://app.aimychats.com/register',
      features: [
        '每月 5 组对话',
        '每组最多 5 个附件',
        '存储空间 1 GB',
        '数据保留 30 天',
        'AI 图片识别',
        'AI 智能摘要',
        '基础智能分析',
        '基础搜索'
      ],
      additionalInfo: '适合个人试用，完整体验核心功能，零门槛上手。'
    },
    {
      name: 'Starter',
      description: '个人用户',
      price: '$4.99',
      period: '/ 月',
      buttonText: '立即订阅',
      buttonLink: 'https://app.aimychats.com/register',
      features: [
        '每月 100 组对话',
        '每组最多 10 个附件',
        '存储空间 5 GB',
        '数据保留 1 年',
        'AI 图片识别',
        'AI 智能摘要',
        '多场景智能分析',
        '高级搜索',
        '元数据自动分析',
        '非图片附件保存与下载',
        '中英西三语智能分析'
      ],
      additionalInfo: '适合日常使用，高性价比，微信、邮件记录全面管理。'
    },
    {
      name: 'Standard',
      description: '专业用户',
      price: '$9.90',
      period: '/ 月',
      buttonText: '立即订阅',
      buttonLink: 'https://app.aimychats.com/register',
      featured: true,
      features: [
        '每月 500 组对话',
        '每组最多 15 个附件',
        '存储空间 10 GB',
        '数据保留 3 年',
        'AI 图片识别',
        'AI 智能摘要',
        '多场景智能分析',
        '高级搜索',
        '元数据自动分析',
        '非图片附件保存与下载',
        '中英西三语智能分析',
        'IMAP 邮件自动收取（即将开放）',
        '智能摘要对接 JIRA（即将开放）'
      ],
      additionalInfo: '适合专业人士和小团队，大量沟通记录长期存档。'
    },
    {
      name: 'Pro',
      description: '企业用户',
      price: '$29.99',
      period: '/ 月',
      buttonText: '立即订阅',
      buttonLink: 'https://app.aimychats.com/register',
      features: [
        '每月 2000 组对话',
        '每组最多 25 个附件',
        '存储空间 20 GB',
        '数据永久保存',
        'AI 图片识别',
        'AI 智能摘要',
        '多场景智能分析',
        '高级搜索',
        '元数据自动分析',
        '非图片附件保存与下载',
        '中英西三语智能分析',
        'IMAP 邮件自动收取（即将开放）',
        '智能摘要对接 JIRA（即将开放）'
      ],
      additionalInfo: '适合企业级数据量，图文结合分析，所有沟通记录永久留存。'
    }
  ],
  note: '所有付费方案均可随时升降级，按月计费，随时取消，无任何违约金。',
  contactCta: {
    title: '需要私有化部署？',
    description: '数据合规、定制规模，或完全私有的运行环境——欢迎聊聊你的需求。',
    buttonText: '联系我们',
    mailto: { user: 'opensource', domain: 'oneprocloud.com', subject: '私有化部署咨询' }
  }
}

const contactData = {
  title: '联系我们',
  subtitle: '两个邮箱，两种用途——找到对的那个。',
  ctaLabel: '发送邮件',
  items: [
    {
      icon: 'deploy',
      title: '开源部署咨询',
      description: '打算自己部署 Devify？我们可以帮你规划方案。',
      user: 'opensource',
      domain: 'oneprocloud.com',
      subject: '开源部署咨询'
    },
    {
      icon: 'support',
      title: '技术支持',
      description: '账户或产品使用中遇到问题？联系我们的支持团队。',
      user: 'support',
      domain: 'oneprocloud.com',
      subject: '技术支持请求'
    }
  ]
}

const footerData = {
  companyName: 'AImyChats',
  companyDescription: '微信聊天记录永不丢失，AI 智能整理，随时找得到。',
  copyright: '',
  productTitle: '产品',
  resourceTitle: '资源',
  companyTitle: '联系我们',
  aboutTitle: '关于',
  socialLinks: [
    { icon: 'github', url: 'https://github.com/cloud2ai/devify', name: 'GitHub' }
  ],
  productLinks: [
    { text: '功能特性', url: '/zh/#features' },
    { text: '价格方案', url: '/zh/#pricing' }
  ],
  resourceLinks: [
    { text: '常见问题', url: '/zh/faq' },
    { text: '微信备份指南', url: '/zh/guide/wechat-backup' }
  ],
  companyLinks: [
    { text: '开源部署咨询', mailto: { user: 'opensource', domain: 'oneprocloud.com' } },
    { text: '技术支持', mailto: { user: 'support', domain: 'oneprocloud.com' } }
  ],
  aboutLinks: [
    { text: '关于我们', url: '/zh/about' }
  ],
  legalLinks: [
    { text: '隐私政策', url: '/zh/privacy' },
    { text: '服务条款', url: '/zh/terms' }
  ]
}
</script>

<Hero v-bind="heroData" />
<Features v-bind="featuresData" />
<WeChatGuide />
<HowItWorks v-bind="howItWorksData" />
<UseCases v-bind="useCasesData" />
<Pricing v-bind="pricingData" />
<OpenSourceBanner
  github-url="https://github.com/cloud2ai/devify"
  badge-text="完全开源"
  heading-line1="AImyChats 背后的引擎"
  heading-line2="Devify 已在 GitHub 开源"
  description="核心处理逻辑、AI 分析流程、邮件接收系统全部代码公开透明。你可以自己部署、审查代码，也可以为项目贡献改进。"
  model-note="不受任何模型厂商锁定——从主流商业模型到 DeepSeek、通义千问等开源模型，均可自由选择、随时切换。"
  code-comment1="AI 解析邮件内容"
  code-comment2="调用 AI 分析"
  view-repo-text="查看 GitHub 仓库"
  star-text="给项目 Star"
/>
<ContactSection v-bind="contactData" />
<Footer v-bind="footerData" />
