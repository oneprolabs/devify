export const getHomeEnContent = () => ({
  heroData: {
    badge: 'WhatsApp + Email → Structured Enterprise Knowledge',
    githubUrl: 'https://github.com/cloud2ai/devify',
    title: 'Your Team\'s Best Knowledge Is Trapped in Chat.<br>Devify Gets It Out.',
    subtitle: 'Customer feedback, engineering decisions, negotiated terms — the conversations where real work happens don\'t live in your docs. Devify turns WhatsApp and email threads into structured records that flow straight into the tools your team already uses.',
    points: [
      {
        icon: 'unified',
        text: 'One inbox for WhatsApp, Slack, Teams, and email'
      },
      {
        icon: 'ai',
        text: 'Reads screenshots and logs, not just text'
      },
      {
        icon: 'search',
        text: 'Every conversation becomes the same structured format'
      },
      {
        icon: 'process',
        text: 'Structured results sync straight into Jira or Feishu Bitable'
      }
    ],
    primaryButtonText: 'Start for Free',
    primaryButtonLink: 'https://app.aimychats.com/register',
    secondaryButtonText: 'See How It Works',
    secondaryButtonLink: '/#features',
    carouselSlides: [
      {
        image: '/images/unified-inbox-en.png',
        alt: 'Email, WhatsApp, WeChat — all flowing into one AI inbox',
        title: 'Every Platform. One Inbox.',
        description:
          'Gmail, WhatsApp, WeChat — all your conversations flow into a single AI-powered archive, organized automatically',
        highlights: ['Multi-platform', 'AI-powered']
      },
      {
        image: '/images/dashboard-list-en.png',
        alt: 'AImyChats - Unified conversation dashboard',
        title: 'All Your Conversations, One Place',
        description:
          'Email threads, WhatsApp chats, WeChat exports — unified and searchable in a single dashboard',
        highlights: ['Unified inbox', 'Instant search']
      },
      {
        image: '/images/ai-analysis-feature.png',
        alt: 'AI extracts summaries, action items, and key decisions',
        title: 'AI Extracts What Actually Matters',
        description:
          'Every conversation automatically summarized, key decisions highlighted, action items pulled out — no manual reading needed',
        highlights: ['Auto summary', 'Structured output']
      }
    ],
    imageSrc: '/images/dashboard-list-en.png',
    imageAlt: 'AImyChats product screenshot',
    features: []
  },
  howItWorksData: {
    title: 'From Scattered Chat to Structured Knowledge',
    subtitle: 'The same four steps behind every conversation Devify processes',
    steps: [
      {
        icon: 'email',
        title: 'Collect — one inbox for every channel',
        description:
          'WhatsApp, Slack, Teams, Gmail, Outlook — forward or connect any of them to a single address. No per-platform integration to build or maintain.'
      },
      {
        icon: 'ai',
        title: 'Understand — text and screenshots alike',
        description:
          'A large share of what matters in a conversation isn\'t text — it\'s a screenshot of an error, a log, a quote. Devify\'s AI reads both and builds the full context.'
      },
      {
        icon: 'dashboard',
        title: 'Standardize — the same shape, regardless of who wrote it',
        description:
          'Some people write a full paragraph; some send five screenshots and no context. Devify turns every conversation into the same structured shape — summary, key points, action items.'
      },
      {
        icon: 'integration',
        title: 'Integrate — into the workflow you already have',
        description:
          'Structured results sync into Jira, Feishu Bitable, or wherever your team already tracks work — so captured knowledge keeps compounding instead of sitting in an archive.'
      }
    ]
  },
  featuresData: {
    title: 'Your Conversations, Finally Under Control',
    subtitle: 'Unified inbox · AI that reads images · Permanent cloud archive',
    features: [
      {
        icon: 'backup',
        title: 'Every Platform, One Place',
        description:
          'Stop switching between Gmail, WhatsApp, and WeChat to piece together what happened. One forward and everything lives in one searchable archive — organized automatically.'
      },
      {
        icon: 'search',
        title: 'Find Anything in Seconds',
        description:
          "Not just keyword search. Multi-dimensional retrieval across senders, dates, topics, and platforms. That contract detail from 18 months ago? Found before you finish typing."
      },
      {
        icon: 'image',
        title: 'AI That Reads Your Screenshots',
        description:
          'Price quotes, contract snapshots, design files, data charts — if it was sent as an image, AI can read it. Screenshot content becomes searchable, summarizable, and actionable.'
      },
      {
        icon: 'backup',
        title: 'Permanent Archive, Zero Maintenance',
        description:
          'WhatsApp media expires. Phones get replaced. Email inboxes get cleared. AImyChats keeps everything indefinitely in the cloud — access it anytime, from any device.'
      }
    ]
  },
  useCasesData: {
    title: 'Built for Teams, Not Just Inboxes',
    subtitle: 'Wherever your team\'s real work happens in chat, Devify turns it into something the whole organization can use',
    useCases: [
      {
        icon: 'team',
        role: 'Engineering Teams',
        subtitle: 'Every bug investigation, captured — not re-solved twice',
        description:
          'The incident chatter in Slack or WhatsApp holds the real root-cause discussion. Devify turns it into a structured record the next on-call engineer can actually find.',
        benefits: [
          'Screenshots, logs, and error messages auto-extracted',
          'Structured issue synced straight to Jira',
          'Search past incidents instead of re-investigating them',
          'Context survives even after the original chat is gone'
        ]
      },
      {
        icon: 'support',
        role: 'Customer Success Teams',
        subtitle: 'Every customer commitment, on record',
        description:
          'Feature requests, complaints, and promises live in WhatsApp threads and forwarded emails. Devify keeps them structured and attributable, instead of buried in one person\'s inbox.',
        benefits: [
          'Customer feedback auto-summarized and tagged',
          'Commitments and deadlines extracted automatically',
          'Synced to your CRM or ticketing system',
          'Full history searchable across every customer'
        ]
      },
      {
        icon: 'lawyer',
        role: 'Compliance & Legal Teams',
        subtitle: 'A defensible record, without changing how anyone communicates',
        description:
          'Regulated communication scattered across chat apps is a liability, not an asset. Devify captures it as structured, timestamped records without asking teams to adopt a new tool.',
        benefits: [
          'Communication captured with full context and timestamps',
          'No new app to adopt — forwarding an email is enough',
          'Structured records exportable for audit',
          'Self-hosted option for full data residency control'
        ]
      }
    ]
  },
  pricingData: {
    title: 'Simple, Honest Pricing',
    subtitle: 'Start free. Upgrade when you need more.',
    featuredLabel: 'Most Popular',
    plans: [
      {
        name: 'Free',
        description: ' ',
        price: '$0',
        period: '/month',
        buttonText: 'Start for Free',
        buttonLink: 'https://app.aimychats.com/register',
        features: [
          '5 conversation groups/month',
          'Up to 5 attachments per group',
          '1 GB storage',
          '30-day retention',
          'AI Image Recognition',
          'AI Smart Summary',
          'Basic Analysis',
          'Basic Search'
        ],
        additionalInfo:
          'Try the full experience with no commitment. Perfect for occasional use.'
      },
      {
        name: 'Starter',
        description: 'Personal Use',
        price: '$4.99',
        period: '/month',
        buttonText: 'Get Started',
        buttonLink: 'https://app.aimychats.com/register',
        features: [
          '100 conversation groups/month',
          'Up to 10 attachments per group',
          '5 GB storage',
          '1-year retention',
          'AI Image Recognition',
          'AI Smart Summary',
          'Multi-Scenario Analysis',
          'Advanced Search',
          'Metadata Auto-Analysis',
          'File Attachment Download',
          'English / Chinese / Spanish Analysis'
        ],
        additionalInfo:
          'Great for individuals managing daily conversations across platforms.'
      },
      {
        name: 'Standard',
        description: 'Professional',
        price: '$9.90',
        period: '/month',
        buttonText: 'Get Started',
        buttonLink: 'https://app.aimychats.com/register',
        featured: true,
        features: [
          '500 conversation groups/month',
          'Up to 15 attachments per group',
          '10 GB storage',
          '3-year retention',
          'AI Image Recognition',
          'AI Smart Summary',
          'Multi-Scenario Analysis',
          'Advanced Search',
          'Metadata Auto-Analysis',
          'File Attachment Download',
          'English / Chinese / Spanish Analysis',
          'IMAP Email Auto-Collection (Coming Soon)',
          'Auto-submit to JIRA (Coming Soon)'
        ],
        additionalInfo:
          'Built for professionals and small teams who need volume, history, and reliability.'
      },
      {
        name: 'Pro',
        description: 'Enterprise',
        price: '$29.99',
        period: '/month',
        buttonText: 'Get Started',
        buttonLink: 'https://app.aimychats.com/register',
        features: [
          '2000 conversation groups/month',
          'Up to 25 attachments per group',
          '20 GB storage',
          'Permanent retention',
          'AI Image Recognition',
          'AI Smart Summary',
          'Multi-Scenario Analysis',
          'Advanced Search',
          'Metadata Auto-Analysis',
          'File Attachment Download',
          'English / Chinese / Spanish Analysis',
          'IMAP Email Auto-Collection (Coming Soon)',
          'Auto-submit to JIRA (Coming Soon)'
        ],
        additionalInfo:
          'For organizations that need maximum volume, permanent archive, and deep AI analysis.'
      }
    ],
    note: 'All plans billed monthly. Upgrade, downgrade, or cancel anytime — no lock-in.',
    contactCta: {
      title: 'Need a private deployment?',
      description: 'Data residency, custom scale, or a fully private environment — let\'s talk about what you need.',
      buttonText: 'Contact us',
      mailto: { user: 'opensource', domain: 'oneprocloud.com', subject: 'Private Deployment Inquiry' }
    }
  },
  contactData: {
    title: 'Talk to a human',
    subtitle: 'Two inboxes, two purposes — reach the right one.',
    ctaLabel: 'Email us',
    items: [
      {
        icon: 'deploy',
        title: 'Open-Source Deployment',
        description: 'Planning to self-host Devify? We can help you scope the setup.',
        user: 'opensource',
        domain: 'oneprocloud.com',
        subject: 'Open-Source Deployment Consulting'
      },
      {
        icon: 'support',
        title: 'Technical Support',
        description: 'Running into an issue with your account or the platform?',
        user: 'support',
        domain: 'oneprocloud.com',
        subject: 'Technical Support Request'
      }
    ]
  },
  footerData: {
    companyName: 'AImyChats',
    companyDescription: 'AI-powered conversation archive. Never lose an important message again.',
    copyright: '',
    productTitle: 'Product',
    resourceTitle: 'Resources',
    companyTitle: 'Contact',
    aboutTitle: 'About',
    socialLinks: [
      { icon: 'github', url: 'https://github.com/cloud2ai/devify', name: 'GitHub' }
    ],
    productLinks: [
      { text: 'Features', url: '/#features' },
      { text: 'Pricing', url: '/#pricing' }
    ],
    resourceLinks: [
      { text: 'FAQ', url: '/en/faq' },
      { text: 'Quick Guide', url: '/en/guide/getting-started' }
    ],
    companyLinks: [
      { text: 'Open-Source Deployment', mailto: { user: 'opensource', domain: 'oneprocloud.com' } },
      { text: 'Technical Support', mailto: { user: 'support', domain: 'oneprocloud.com' } }
    ],
    aboutLinks: [
      { text: 'About Us', url: '/en/about' }
    ],
    legalLinks: [
      { text: 'Privacy', url: '/en/privacy' },
      { text: 'Terms', url: '/en/terms' }
    ]
  }
})
