# Devify UI

> **AimyChats** - 一个支持中英文双语、时区感知的、AI驱动的邮件对话摘要应用。

Devify 项目的前端应用，以 AimyChats 品牌对外展示。

## 功能特性

- 🌍 **多语言支持** - 支持中文和英文，可轻松扩展更多语言
- 🕐 **时区感知** - 自动检测用户时区，所有时间按用户时区显示
- 🤖 **AI 摘要** - 自动生成邮件对话摘要
- 📧 **邮件转发** - 将聊天记录转发到专属邮箱即可自动处理
- 🔐 **用户认证** - JWT 基础的安全认证系统
- 📱 **响应式设计** - 完美适配桌面端和移动端
- ♿ **无障碍访问** - 符合 WCAG AA 标准

## 技术栈

- **前端框架**: Vue 3 (Composition API)
- **构建工具**: Vite
- **样式**: Tailwind CSS
- **状态管理**: Pinia
- **路由**: Vue Router
- **国际化**: vue-i18next
- **UI组件**: Headless UI
- **日期处理**: date-fns + date-fns-tz
- **HTTP客户端**: Axios

## 项目结构

```
src/
├── api/                    # API层
│   ├── index.js           # Axios配置和拦截器
│   ├── auth.js            # 认证API
│   ├── chat.js            # 对话API
│   └── settings.js        # 设置API
├── components/            # 可复用组件
│   ├── ui/               # 基础UI组件
│   └── layout/           # 布局组件
├── pages/                # 页面组件
│   ├── Login.vue         # 登录页
│   ├── Register.vue      # 注册页
│   ├── Dashboard.vue     # 对话列表页
│   ├── ThreadlineDetail.vue  # 对话详情页
│   ├── Settings.vue      # 设置页
│   └── NotFound.vue      # 404页面
├── store/                # Pinia stores
│   ├── user.js          # 用户状态
│   └── preferences.js   # 用户偏好（语言、时区）
├── router/               # Vue Router配置
│   └── index.js
├── i18n/                 # 国际化配置
│   └── index.js
├── locales/              # 语言资源文件
│   ├── en.json          # 英语
│   └── zh-CN.json       # 简体中文
├── utils/                # 工具函数
│   └── timezone.js      # 时区工具
├── assets/               # 静态资源
│   └── css/             # 全局样式
├── App.vue              # 根组件
└── main.js              # 应用入口
```

## 开始使用

### 环境要求

- Node.js 22.x (LTS) 或更高版本
- npm 或 yarn
- 后端 API 运行在 `http://localhost:8000`

### 安装

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问应用
# 打开浏览器访问 http://localhost:5173
```

### 构建生产版本

```bash
# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

### 代码检查

```bash
# 运行 ESLint
npm run lint
```

## 核心功能

### 1. 认证系统

- **注册**: 新用户可以创建账户，系统自动检测浏览器语言和时区
- **登录**: JWT 基础的安全登录
- **记住我**: 可选的会话持久化
- **语言切换**: 登录页面可以切换界面语言

### 2. 对话列表

- 显示所有邮件对话的 AI 摘要
- 统计卡片：总消息数、本周消息、待处理、已完成
- 搜索和过滤功能
- 时间按用户时区显示

### 3. 对话详情

- 查看 AI 生成的摘要标题和内容
- 查看原始邮件内容（HTML/文本视图）
- 查看和预览附件
- 复制功能（摘要、原文、链接）
- **邮件重试功能**：支持对所有状态的邮件进行重试处理
  - 可以选择处理语言和场景进行重新处理
  - 支持强制重试模式（会重新识别图片和调用LLM）
  - 自动轮询状态，等待处理完成
  - 重试过程中按钮保持loading状态，防止重复操作

### 4. 设置

- **邮箱地址**: 显示专属邮箱地址，一键复制
- **语言设置**: 切换中文/英文界面
- **时区设置**: 选择您的时区，自动显示检测结果

## 后端 API 集成

### 认证端点

- `POST /api/v1/auth/login` - 登录
- `POST /api/v1/auth/registration` - 注册
- `GET /api/v1/auth/user` - 获取用户信息
- `POST /api/v1/auth/logout` - 登出

### 对话端点

- `GET /api/v1/threadline/threadlines` - 获取对话列表
- `GET /api/v1/threadline/threadlines/:id` - 获取对话详情
- `PATCH /api/v1/threadline/threadlines/:id` - 更新对话
- `POST /api/v1/threadline/threadlines/:id/retry` - 重试邮件处理
  - 请求参数：
    - `language` (可选): 处理语言（如 'zh-CN', 'en-US'）
    - `scene` (可选): 处理场景（如 'chat', 'product_issue'）
    - `force` (可选, 默认false): 强制重试，会重新识别图片和调用LLM
  - 返回：任务已触发的确认信息

### 设置端点

- `GET /api/v1/threadline/settings` - 获取设置列表
- `POST /api/v1/threadline/settings` - 创建设置
- `PATCH /api/v1/threadline/settings/:id` - 更新设置

## 国际化

应用支持中英文双语，可以轻松扩展到更多语言。

### 添加新语言

1. 在 `src/locales/` 目录下创建新的语言文件，例如 `ja.json`
2. 复制 `en.json` 的内容并翻译
3. 在 `src/i18n/index.js` 中导入新语言文件
4. 在 `src/utils/timezone.js` 中添加对应的 date-fns locale

### 使用翻译

```vue
<template>
  <div>{{ t('common.appName') }}</div>
</template>

<script setup>
import { useTranslation } from 'vue-i18next'

const { t } = useTranslation()
</script>
```

## 时区处理

所有时间显示都会自动转换为用户设置的时区。

### 格式化日期

```javascript
import { formatDate, formatRelativeTime } from '@/utils/timezone'
import { usePreferencesStore } from '@/store/preferences'

const preferencesStore = usePreferencesStore()

// 格式化为特定格式
const formatted = formatDate(
  dateString,
  preferencesStore.currentTimezone,
  'yyyy-MM-dd HH:mm',
  preferencesStore.currentLanguage
)

// 相对时间（"2小时前"）
const relative = formatRelativeTime(
  dateString,
  preferencesStore.currentLanguage
)
```

## 环境变量

创建 `.env` 文件：

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_APP_TITLE=AimyChats
```

## 开发指南

### 代码风格

- 使用 ESLint 和 Prettier 进行代码格式化
- 遵循 Vue 3 Composition API 模式
- 使用 `<script setup>` 语法
- 编写描述性的组件名称

### 组件结构

```vue
<template>
  <!-- 模板内容 -->
</template>

<script setup>
// 脚本内容
</script>

<style scoped>
/* 组件样式 */
</style>
```

### 状态管理

- 使用 Pinia 管理全局状态
- 尽可能保持组件状态本地化
- 使用 computed 属性处理派生状态

## 浏览器支持

- Chrome 88+
- Firefox 85+
- Safari 14+
- Edge 88+

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

[Apache License 2.0](LICENSE)
