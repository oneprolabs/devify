<template>
  <div class="oss-wrapper">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="oss-card">
        <div class="oss-left">
          <div class="oss-badge">
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
            </svg>
            {{ badgeText }}
          </div>
          <h2 class="oss-title">
            {{ headingLine1 }}<br>
            <span class="oss-highlight">{{ headingLine2 }}</span>
          </h2>
          <p class="oss-desc">{{ description }}</p>
          <div v-if="modelNote" class="oss-model-note">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span>{{ modelNote }}</span>
          </div>
          <div class="oss-actions">
            <a :href="githubUrl" target="_blank" rel="noopener" class="oss-btn-primary">
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
              </svg>
              {{ viewRepoText }}
            </a>
            <a :href="githubUrl" target="_blank" rel="noopener" class="oss-btn-secondary">
              ⭐ {{ starText }}
            </a>
          </div>
        </div>
        <div class="oss-right">
          <div class="code-preview">
            <div class="code-header">
              <div class="code-dots">
                <span></span><span></span><span></span>
              </div>
              <span class="code-filename">devify / billing / webhook</span>
            </div>
            <pre class="code-body"><span class="c-purple">@webhook_handler</span>
<span class="c-blue">def</span> <span class="c-green">process_email</span>(email):
    <span class="c-gray"># {{ codeComment1 }}</span>
    content = <span class="c-green">extract_content</span>(email)
    images = <span class="c-green">parse_attachments</span>(email)

    <span class="c-gray"># {{ codeComment2 }}</span>
    result = <span class="c-green">ai_analyze</span>(
        text=content,
        images=images
    )
    <span class="c-blue">return</span> result.summary</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  githubUrl: {
    type: String,
    default: 'https://github.com/cloud2ai/devify'
  },
  badgeText: {
    type: String,
    default: 'Open Source'
  },
  headingLine1: {
    type: String,
    default: 'The engine behind AImyChats'
  },
  headingLine2: {
    type: String,
    default: 'Devify is open source on GitHub'
  },
  description: {
    type: String,
    default: 'The full processing pipeline — AI analysis, email ingestion, webhook handling — is open and auditable. Self-host it, inspect it, or contribute improvements.'
  },
  modelNote: {
    type: String,
    default: 'No vendor lock-in on the model layer — bring anything from mainstream commercial models to affordable open alternatives like DeepSeek or Qwen, and switch anytime.'
  },
  codeComment1: {
    type: String,
    default: 'parse email content'
  },
  codeComment2: {
    type: String,
    default: 'run AI analysis'
  },
  viewRepoText: {
    type: String,
    default: 'View on GitHub'
  },
  starText: {
    type: String,
    default: 'Star this project'
  }
})
</script>

<style scoped>
.oss-wrapper {
  padding: 4rem 0;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
  position: relative;
  overflow: hidden;
}

.oss-wrapper::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 50%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
    radial-gradient(circle at 80% 50%, rgba(139, 92, 246, 0.1) 0%, transparent 50%);
}

.oss-card {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3rem;
  align-items: center;
}

@media (max-width: 768px) {
  .oss-card {
    grid-template-columns: 1fr;
    gap: 2rem;
  }
  .oss-right {
    display: none;
  }
}

.oss-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.9rem;
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.4);
  border-radius: 999px;
  color: #a5b4fc;
  font-size: 0.8rem;
  font-weight: 600;
  margin-bottom: 1.25rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.oss-title {
  font-size: 2rem;
  font-weight: 800;
  color: white;
  line-height: 1.3;
  margin-bottom: 1rem;
}

@media (min-width: 768px) {
  .oss-title {
    font-size: 2.25rem;
  }
}

.oss-highlight {
  background: linear-gradient(90deg, #818cf8, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.oss-desc {
  color: #94a3b8;
  font-size: 1rem;
  line-height: 1.7;
  margin-bottom: 1.75rem;
}

.oss-model-note {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.85rem 1rem;
  margin-bottom: 1.75rem;
  border-radius: 0.6rem;
  background: rgba(129, 140, 248, 0.08);
  border-left: 2px solid #818cf8;
  color: #c7d2fe;
  font-size: 0.85rem;
  line-height: 1.6;
}

.oss-model-note svg {
  color: #a5b4fc;
  margin-top: 0.15rem;
}

.oss-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.oss-btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.4rem;
  background: white;
  color: #0f172a;
  border-radius: 0.5rem;
  font-weight: 600;
  font-size: 0.9rem;
  text-decoration: none;
  transition: all 0.2s;
}

.oss-btn-primary:hover {
  background: #f1f5f9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.oss-btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.4rem;
  background: transparent;
  color: #e2e8f0;
  border: 1px solid rgba(226, 232, 240, 0.25);
  border-radius: 0.5rem;
  font-weight: 500;
  font-size: 0.9rem;
  text-decoration: none;
  transition: all 0.2s;
}

.oss-btn-secondary:hover {
  background: rgba(255,255,255,0.07);
  border-color: rgba(226, 232, 240, 0.5);
}

/* Code preview */
.code-preview {
  background: #0d1117;
  border-radius: 0.75rem;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 20px 40px rgba(0,0,0,0.4);
}

.code-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: #161b22;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.code-dots {
  display: flex;
  gap: 5px;
}

.code-dots span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #30363d;
}

.code-dots span:nth-child(1) { background: #ff5f57; }
.code-dots span:nth-child(2) { background: #febc2e; }
.code-dots span:nth-child(3) { background: #28c840; }

.code-filename {
  color: #8b949e;
  font-size: 0.78rem;
  font-family: monospace;
}

.code-body {
  padding: 1.25rem 1.5rem;
  font-family: 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  line-height: 1.8;
  color: #e6edf3;
  margin: 0;
  white-space: pre;
}

.c-purple { color: #d2a8ff; }
.c-blue   { color: #79c0ff; }
.c-green  { color: #7ee787; }
.c-gray   { color: #8b949e; }
</style>
