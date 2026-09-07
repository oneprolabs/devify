# Devify Homepage - 快速开始

## 项目概述

这是 Devify 的产品首页和文档网站，使用 VitePress 构建。

### 特点

- ✅ 响应式设计（移动优先）
- ✅ 中英文双语支持
- ✅ 差异化内容定位
  - 中文版：微信聊天备份 + AI 智能助手
  - 英文版：AI-Powered Conversation Hub（多渠道汇总）
- ✅ 自定义 Vue 组件
- ✅ Tailwind CSS 集成
- ✅ SEO 优化

## 本地开发

### 1. 安装依赖

```bash
cd /home/ubuntu/workspace/devify_workspace/devify-home
npm install
```

### 2. 启动开发服务器

```bash
npm run docs:dev
```

访问：http://localhost:5173

默认显示中文首页：http://localhost:5173/zh/
英文首页：http://localhost:5173/en/

### 3. 构建生产版本

```bash
npm run docs:build
```

构建输出在 `docs/.vitepress/dist/`

### 4. 预览生产构建

```bash
npm run docs:preview
```

## 项目结构

```
devify-home/
├── docs/
│   ├── .vitepress/
│   │   ├── config.js              # VitePress 配置（多语言）
│   │   └── theme/
│   │       ├── index.js           # 主题入口
│   │       ├── components/        # 自定义组件
│   │       │   ├── Hero.vue      # 首页 Hero 区域
│   │       │   ├── Features.vue  # 功能展示
│   │       │   ├── Pricing.vue   # 价格表
│   │       │   ├── Footer.vue    # 页脚
│   │       │   └── MobileNav.vue # 移动端导航
│   │       └── styles/
│   │           └── custom.css     # Tailwind + 自定义样式
│   │
│   ├── zh/                        # 中文内容
│   │   ├── index.md              # 首页（微信备份主题）
│   │   ├── guide/
│   │   │   ├── wechat-backup.md # 微信备份指南
│   │   │   └── features.md      # 功能说明
│   │   ├── pricing.md            # 价格
│   │   └── faq.md                # 常见问题
│   │
│   ├── en/                        # 英文内容
│   │   ├── index.md              # 首页（Conversation Hub 主题）
│   │   ├── guide/
│   │   │   ├── getting-started.md    # 快速开始
│   │   │   └── integrations.md       # 集成指南
│   │   ├── pricing.md            # Pricing
│   │   └── faq.md                # FAQ
│   │
│   ├── api/                       # API 文档（共享）
│   │   ├── authentication.md     # 认证
│   │   ├── webhooks.md           # Webhooks
│   │   └── reference.md          # API 参考
│   │
│   └── public/                    # 静态资源
│       ├── logo.svg
│       └── images/
│
├── package.json
├── tailwind.config.js
├── postcss.config.js
└── README.md
```

## 自定义组件使用

### Hero 组件

```vue
<Hero 
  badge="安全可靠"
  title="产品标题"
  subtitle="产品副标题"
  primaryButtonText="立即开始"
  primaryButtonLink="#"
  secondaryButtonText="了解更多"
  secondaryButtonLink="#"
  imageSrc="/images/screenshot.png"
  :features="['功能1', '功能2']"
/>
```

### Features 组件

```vue
<Features 
  title="核心功能"
  subtitle="功能说明"
  :features="[
    {
      icon: 'backup',
      title: '自动备份',
      description: '描述...'
    }
  ]"
/>
```

### Pricing 组件

```vue
<Pricing 
  title="选择方案"
  subtitle="灵活定价"
  featuredLabel="最受欢迎"
  :plans="[
    {
      name: 'Free',
      price: '¥0',
      period: '/月',
      featured: false,
      features: ['功能1', '功能2']
    }
  ]"
/>
```

## 内容更新

### 更新中文内容

编辑 `docs/zh/` 目录下的文件

### 更新英文内容

编辑 `docs/en/` 目录下的文件

### 更新 API 文档

编辑 `docs/api/` 目录下的文件（中英文共享）

## 价格方案参考

基于现有的订阅计划：

| 计划 | 价格（中文） | 价格（英文） | 邮件数 | 存储 |
|------|------------|------------|--------|------|
| Free | ¥0 | $0 | 5/月 | 10MB |
| Basic | ¥35 | $4.99 | 10/月 | 50MB |
| Professional | ¥69 | $9.90 | 20/月 | 200MB |
| Enterprise | ¥209 | $29.99 | 500/月 | 1000MB |

## 样式定制

### Tailwind 配置

编辑 `tailwind.config.js` 修改主题颜色、字体等

### 自定义样式

编辑 `docs/.vitepress/theme/styles/custom.css`

## 移动端适配

所有组件已经优化移动端显示：

- 响应式断点：mobile (< 640px), tablet (640-1024px), desktop (> 1024px)
- 触摸区域最小 44x44px
- 汉堡菜单导航
- 价格表支持左右滑动

## 下一步

### 待添加内容

1. **产品截图**：将实际产品截图放在 `docs/public/images/` 目录
2. **Favicon**：添加 `docs/public/favicon.ico`
3. **社交媒体链接**：更新 Footer 组件中的链接
4. **实际的注册/登录链接**：更新 CTA 按钮链接

### 生产部署

当需要部署时：

1. 创建 Dockerfile（参考 devify-ui）
2. 添加到 docker-compose.yml
3. 配置 nginx 反向代理

## 技术支持

如有问题，请参考：
- VitePress 文档：https://vitepress.dev
- Tailwind CSS 文档：https://tailwindcss.com
- Vue 3 文档：https://vuejs.org

