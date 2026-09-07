# AImyChats Homepage

Official product homepage and documentation for AImyChats (aimychats.com).

## About

AImyChats is an AI-powered email assistant platform:

- **Chinese version**: Focus on AI email assistant (微信聊天备份 + AI 智能助手)
- **English version**: Focus on AI email assistant (multi-channel email management)

## Tech Stack

- **VitePress**: Static site generator
- **Vue 3**: Component framework
- **Tailwind CSS**: Styling
- **Markdown**: Documentation

## Getting Started

### Install Dependencies

```bash
npm install
```

### Development

```bash
npm run docs:dev
```

Visit http://localhost:5173

### Build

```bash
npm run docs:build
```

### Preview Production Build

```bash
npm run docs:preview
```

## Project Structure

```
docs/
├── .vitepress/
│   ├── config.js           # VitePress configuration
│   └── theme/              # Custom theme
│       ├── components/     # Vue components
│       └── styles/         # Custom styles
├── zh/                     # Chinese content
│   ├── index.md           # Homepage
│   ├── guide/             # Guides
│   ├── pricing.md         # Pricing
│   └── faq.md             # FAQ
├── en/                     # English content
│   ├── index.md           # Homepage
│   ├── guide/             # Guides
│   ├── pricing.md         # Pricing
│   └── faq.md             # FAQ
├── api/                    # API documentation (shared)
│   ├── authentication.md
│   ├── webhooks.md
│   └── reference.md
└── public/                 # Static assets
    └── images/
```

## Features

- ✅ Responsive design (mobile-first)
- ✅ Multi-language support (Chinese/English)
- ✅ Differentiated content for each language
- ✅ Custom Vue components
- ✅ Tailwind CSS integration
- ✅ SEO optimized

## License

MIT
