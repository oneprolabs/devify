<template>
  <div class="wechat-guide-wrapper py-16 md:py-24">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="text-center mb-12 md:mb-16">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-green-100 text-green-700 text-sm font-medium mb-4">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8.5 3C5.46 3 3 5.46 3 8.5c0 1.74.81 3.29 2.07 4.32L4 14l1.57-.52C6.54 14.14 7.49 14.5 8.5 14.5c.27 0 .54-.02.8-.05C9.12 14.96 9 15.47 9 16c0 2.76 2.24 5 5 5s5-2.24 5-5-2.24-5-5-5c-.53 0-1.04.12-1.55.3.03-.26.05-.53.05-.8C12.5 5.46 10.04 3 8.5 3z"/>
          </svg>
          微信专属指引
        </div>
        <h2 class="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-900 mb-4">
          三步转发微信聊天记录
        </h2>
        <p class="text-lg md:text-xl text-gray-500 max-w-2xl mx-auto">
          无需安装任何插件，在微信内即可完成操作
        </p>
      </div>

      <!-- Steps with phone mockups -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-6 items-start">

        <!-- Step 1 -->
        <div class="step-item">
          <div class="step-number">1</div>
          <div class="phone-mockup">
            <div class="phone-frame">
              <div class="phone-screen">
                <!-- WeChat Chat List -->
                <div class="wechat-header">
                  <span class="wechat-title">微信</span>
                </div>
                <div class="chat-list">
                  <div class="chat-row active-row">
                    <div class="chat-avatar" style="background:#07c160">项</div>
                    <div class="chat-info">
                      <div class="chat-name">项目讨论群</div>
                      <div class="chat-preview">好的，明天上午10点确认</div>
                    </div>
                    <div class="chat-time">刚刚</div>
                  </div>
                  <div class="chat-row">
                    <div class="chat-avatar" style="background:#576b95">张</div>
                    <div class="chat-info">
                      <div class="chat-name">张总</div>
                      <div class="chat-preview">[图片]</div>
                    </div>
                    <div class="chat-time">昨天</div>
                  </div>
                  <div class="chat-row">
                    <div class="chat-avatar" style="background:#fa9d3b">客</div>
                    <div class="chat-info">
                      <div class="chat-name">客户王女士</div>
                      <div class="chat-preview">合同已签，请查收</div>
                    </div>
                    <div class="chat-time">周一</div>
                  </div>
                </div>
                <!-- Tap hint -->
                <div class="tap-hint">
                  <div class="tap-circle pulse-ring"></div>
                </div>
              </div>
            </div>
          </div>
          <div class="step-label">
            <h3>选择要备份的聊天</h3>
            <p>打开微信，点击任意需要保存的对话</p>
          </div>
        </div>

        <!-- Arrow -->
        <div class="step-arrow md:mt-32">→</div>

        <!-- Step 2 -->
        <div class="step-item">
          <div class="step-number">2</div>
          <div class="phone-mockup">
            <div class="phone-frame">
              <div class="phone-screen">
                <!-- WeChat Chat View -->
                <div class="wechat-header chat-nav">
                  <span class="back-btn">‹</span>
                  <span class="wechat-title">项目讨论群</span>
                  <span class="dots-btn highlighted-btn">•••</span>
                </div>
                <div class="chat-messages">
                  <div class="msg-bubble msg-other">好的，明天上午10点确认方案</div>
                  <div class="msg-bubble msg-self">收到，我来整理会议纪要</div>
                  <div class="msg-bubble msg-other">
                    <div class="img-placeholder">
                      <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01"/></svg>
                    </div>
                  </div>
                </div>
                <div class="highlight-arrow-top">← 点击右上角</div>
              </div>
            </div>
          </div>
          <div class="step-label">
            <h3>点击右上角「···」</h3>
            <p>在聊天页面右上角找到三个点的菜单按钮</p>
          </div>
        </div>

        <!-- Arrow -->
        <div class="step-arrow md:mt-32">→</div>

        <!-- Step 3 -->
        <div class="step-item">
          <div class="step-number">3</div>
          <div class="phone-mockup">
            <div class="phone-frame">
              <div class="phone-screen">
                <!-- WeChat Options Menu -->
                <div class="wechat-header chat-nav">
                  <span class="back-btn">‹</span>
                  <span class="wechat-title">项目讨论群</span>
                  <span class="dots-btn">•••</span>
                </div>
                <div class="options-overlay">
                  <div class="option-row highlighted-option">
                    <div class="option-icon email-icon">
                      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                      </svg>
                    </div>
                    <span class="option-text">邮件传输聊天记录</span>
                    <div class="tap-dot"></div>
                  </div>
                  <div class="option-row">
                    <div class="option-icon">
                      <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                      </svg>
                    </div>
                    <span class="option-text text-gray-500">搜索聊天记录</span>
                  </div>
                  <div class="option-row">
                    <div class="option-icon">
                      <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                      </svg>
                    </div>
                    <span class="option-text text-gray-500">清空聊天记录</span>
                  </div>
                  <div class="email-fill-hint">
                    发送到你的专属邮箱：<br/>
                    <span class="email-addr">xxx@aimychats.com</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="step-label">
            <h3>转发到专属邮箱</h3>
            <p>选择「邮件传输聊天记录」，收件人填写你的 AImyChats 专属邮箱地址</p>
          </div>
        </div>

      </div>

      <!-- Bottom tip -->
      <div class="bottom-tip">
        <svg class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span>专属邮箱地址在注册后的账户设置页面可以找到。支持微信、邮件、截图等任意形式的聊天记录，发到这个邮箱就会自动处理。</span>
      </div>
    </div>
  </div>
</template>

<script setup></script>

<style scoped>
.wechat-guide-wrapper {
  background: #ffffff;
}

.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  position: relative;
}

.step-number {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  background: #07c160;
  color: white;
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(7, 193, 96, 0.35);
}

.step-arrow {
  display: none;
  font-size: 2rem;
  color: #07c160;
  font-weight: 300;
  align-items: center;
  justify-content: center;
}

@media (min-width: 768px) {
  .step-arrow {
    display: flex;
  }
}

/* Phone mockup */
.phone-mockup {
  display: flex;
  justify-content: center;
}

.phone-frame {
  width: 180px;
  background: #1a1a2e;
  border-radius: 28px;
  padding: 10px 8px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.25), 0 0 0 2px #333;
  position: relative;
}

.phone-frame::before {
  content: '';
  display: block;
  width: 60px;
  height: 6px;
  background: #333;
  border-radius: 3px;
  margin: 0 auto 8px;
}

.phone-screen {
  background: #f5f5f5;
  border-radius: 20px;
  overflow: hidden;
  min-height: 280px;
  position: relative;
}

/* WeChat UI Elements */
.wechat-header {
  background: #ededed;
  padding: 8px 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #ddd;
}

.chat-nav {
  justify-content: space-between;
}

.wechat-title {
  font-size: 12px;
  font-weight: 600;
  color: #1a1a1a;
}

.back-btn {
  font-size: 18px;
  color: #576b95;
  line-height: 1;
}

.dots-btn {
  font-size: 10px;
  color: #576b95;
  letter-spacing: 1px;
  padding: 2px 4px;
  border-radius: 3px;
}

.highlighted-btn {
  background: rgba(7, 193, 96, 0.2);
  color: #07c160;
  animation: pulse-btn 1.5s ease-in-out infinite;
}

@keyframes pulse-btn {
  0%, 100% { background: rgba(7, 193, 96, 0.15); }
  50% { background: rgba(7, 193, 96, 0.35); }
}

/* Chat list */
.chat-list {
  padding: 0;
}

.chat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
  position: relative;
}

.active-row {
  background: #d4efdf;
}

.chat-avatar {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.chat-info {
  flex: 1;
  min-width: 0;
}

.chat-name {
  font-size: 10px;
  font-weight: 600;
  color: #1a1a1a;
}

.chat-preview {
  font-size: 9px;
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-time {
  font-size: 8px;
  color: #aaa;
  flex-shrink: 0;
}

/* Tap hint */
.tap-hint {
  position: absolute;
  top: 58px;
  left: 18px;
}

.tap-circle {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(7, 193, 96, 0.4);
  border: 2px solid #07c160;
}

.pulse-ring {
  animation: pulse-ring 1.5s ease-in-out infinite;
}

@keyframes pulse-ring {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.6; }
  100% { transform: scale(1); opacity: 1; }
}

/* Chat messages */
.chat-messages {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #f0f0f0;
  min-height: 160px;
}

.msg-bubble {
  max-width: 75%;
  padding: 5px 8px;
  border-radius: 6px;
  font-size: 9px;
  line-height: 1.4;
  color: #1a1a1a;
}

.msg-other {
  background: white;
  align-self: flex-start;
  border-radius: 2px 6px 6px 6px;
}

.msg-self {
  background: #07c160;
  color: white;
  align-self: flex-end;
  border-radius: 6px 2px 6px 6px;
}

.img-placeholder {
  width: 50px;
  height: 40px;
  background: #e0e0e0;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.highlight-arrow-top {
  position: absolute;
  top: 28px;
  right: 6px;
  font-size: 8px;
  color: #07c160;
  font-weight: 600;
  white-space: nowrap;
}

/* Options overlay */
.options-overlay {
  padding: 6px 0;
  background: white;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #f5f5f5;
  position: relative;
}

.highlighted-option {
  background: #f0fdf4;
  border-left: 3px solid #07c160;
}

.option-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.email-icon {
  background: #07c160;
  color: white;
}

.email-icon svg {
  color: white;
}

.option-text {
  font-size: 9px;
  color: #1a1a1a;
  font-weight: 500;
  flex: 1;
}

.tap-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(7, 193, 96, 0.5);
  border: 2px solid #07c160;
  animation: pulse-ring 1.5s ease-in-out infinite;
}

.email-fill-hint {
  margin: 8px 12px 4px;
  font-size: 8px;
  color: #666;
  line-height: 1.5;
  padding: 6px 8px;
  background: #f8f8f8;
  border-radius: 6px;
  border: 1px dashed #07c160;
}

.email-addr {
  color: #07c160;
  font-weight: 600;
  word-break: break-all;
}

/* Step label */
.step-label {
  text-align: center;
  max-width: 200px;
}

.step-label h3 {
  font-size: 1rem;
  font-weight: 700;
  color: #1a1a1a;
  margin-bottom: 0.25rem;
}

.step-label p {
  font-size: 0.85rem;
  color: #6b7280;
  line-height: 1.5;
}

/* Bottom tip */
.bottom-tip {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-top: 3rem;
  padding: 1rem 1.5rem;
  background: white;
  border: 1px solid #bbf7d0;
  border-radius: 0.75rem;
  font-size: 0.9rem;
  color: #374151;
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
  box-shadow: 0 2px 8px rgba(7, 193, 96, 0.08);
}

/* Mobile layout */
@media (max-width: 767px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .step-arrow {
    display: none;
  }

  .step-item::after {
    content: '↓';
    font-size: 1.5rem;
    color: #07c160;
    display: block;
    text-align: center;
    margin-top: 0.5rem;
  }

  .step-item:last-child::after {
    display: none;
  }
}

/* Grid override for desktop - 3+arrow+3+arrow+3 = need custom grid */
@media (min-width: 768px) {
  .grid {
    display: grid;
    grid-template-columns: 1fr auto 1fr auto 1fr;
    align-items: start;
  }
}
</style>
