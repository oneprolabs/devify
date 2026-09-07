<style>
/* ======== FAQ 页面标题微调 ======== */

/* H1 大标题 */
.vp-doc h1 {
  font-size: 1.5rem !important;
  line-height: 1.4 !important;
  font-weight: 700 !important;
  margin: 1.5rem 0 2.5rem 0 !important;
}

/* H2 二级标题 */
.vp-doc h2 {
  font-size: 1.05rem !important; /* 比三级标题(0.9rem)大 */
  line-height: 1.4 !important;
  font-weight: 600 !important;
  margin: 0.5rem 0 0.4rem 0 !important;
  border-top: none !important;
  border-bottom: 1px solid #e5e7eb !important;
  padding-bottom: 0.3rem !important;
}

/* H3 三级标题 */
.vp-doc h3 {
  font-size: 0.9rem !important;
  line-height: 1.4 !important;
  font-weight: 600 !important;
  margin: 1rem 0 0.6rem 0 !important;
}

/* ======== FAQ 列表样式 ======== */
.vp-doc details {
  margin: 6px 0 !important;
}

/* details summary 标题 */
.vp-doc details > summary {
  cursor: pointer !important;
  font-size: 0.95rem !important;
  font-weight: 600 !important;
  line-height: 1.5 !important;
  margin: 8px 0 !important;
  list-style: none !important;
}

.vp-doc details > summary::-webkit-details-marker {
  display: none !important;
}

/* 自定义箭头 */
.vp-doc details > summary::before {
  content: "";
  display: inline-block;
  width: 6px;
  height: 6px;
  border-right: 2px solid #6B7280;
  border-bottom: 2px solid #6B7280;
  transform: rotate(-45deg);
  margin-right: 10px;
  transition: transform 0.2s ease;
}

.vp-doc details[open] > summary::before {
  transform: rotate(45deg);
}

/* details 内容 */
.vp-doc details > div {
  margin: 12px 0 !important;
  padding-left: 12px !important;
  border-left: 3px solid #F3F4F6 !important;
  line-height: 1.6 !important;
  font-size: 0.9rem !important;
}



/* 列表整体缩进: 标记前空2格 */
.vp-doc ul {
  padding-left: 2em !important;
}

/* 嵌套列表样式: 空心圆 (二级) */
.vp-doc ul > li > ul {
  list-style-type: circle !important;
}

/* 嵌套列表样式: 方块 (三级) */
.vp-doc ul > li > ul > li > ul {
  list-style-type: square !important;
}
</style>

<span id="top"></span>
# 📚 AImyChats 常见问题 (FAQ)

<div style="margin:16px 0; padding:16px 20px; padding-left:20px; border-left:4px solid #3B82F6; background-color:#F8FAFC; border-radius:6px; font-size: 0.95rem; line-height: 1.8;">
  <div style="margin-bottom:8px; font-weight:600; color:#1E40AF;">
    🔥 <strong>AImyChats</strong>
  </div>
  <div style="color:#475569; padding-left:4px;">
    智能管理你的多平台聊天记录，自动备份、归类与摘要，重要对话随手可查，信息安全可靠。
  </div>
</div>




## 🚀 核心价值
<details>
<summary>1. AImyChats 能帮我做什么？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

AImyChats 是一个专为微信聊天设计的智能备份平台，帮助您：

- **永久保存**重要的微信对话（文字、图片、文件等）
- **AI自动生成**对话摘要，快速回顾核心内容
- **智能搜索**所有历史聊天记录，随时查找信息
- **云端安全存储**，释放手机空间

【[立即免费试用，体验智能备份](https://app.aimychats.com/register)】

</div>
</details>

<details>
<summary>2. 如何将微信聊天备份并生成AI摘要？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

只需3步，即可实现永久备份：

**第1步：获取专属接收地址**

- 登录 AImyChats 平台
- 点击右上角个人头像
- 复制您的专属邮箱地址（格式：**xxx@aimychats.com**）

**第2步：配置微信邮件发送功能（一次设置，长期使用）**
- 【推荐】使用"QQ邮箱"：在微信内搜索“QQ邮箱提醒”，启用并登录QQ邮箱即可。这是最便捷的方式。

**第3步：选择并发送聊天内容**
- 在微信中勾选需要备份的消息（可多选）
- 点击右下角 … → 【转发到邮件】
- 在收件人栏粘贴您的专属地址，发送

✅ **完成！** 稍等片刻，即可在 AImyChats 查看完整记录和AI生成的智能摘要。

💡 **温馨提示：** 同时勾选相关的图片和文件，AI生成的摘要会更全面、更准确。

</div>
</details>

<details>
<summary>3. 我的数据安全吗？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**绝对安全。**  我们采用银行级别的多重加密保护：

- **传输加密：** 所有数据传输均使用 HTTPS/TLS 1.3 加密
- **存储加密：** 云端存储采用 AES-256 军事级加密
- **访问控制：** 只有您本人可通过账号密码访问自己的数据
- **定期审计：** 通过第三方安全机构定期进行安全审计
- **多地备份：** 数据在多个地理位置备份，防止意外丢失

**我们承诺：** 您的私密对话仅为您可见，AI处理过程也完全在加密环境中进行。

</div>
</details>

<details>
<summary>4. AI摘要准确吗？能信任吗？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

我们的AI摘要功能具有**高准确率和完全可控性：**

- **行业领先的准确率：** 基于先进的AI大模型，对常规对话的摘要准确率超过 92%
- **覆盖多种场景：** 适合工作汇报、项目讨论、学习交流、重要约定等多种对话类型
- **您可以完全控制：**
  - 生成后可随时一键编辑修改摘要
  - 对于不满意的摘要，可重新生成
  - 可选择是否在摘要中包含时间、人物等元信息

**需要注意的情况：**
- 对话内容过短
- 包含大量专业术语或代码
- 多语言混合对话

在这些情况下，您可能需要手动微调摘要。但无论如何，**原始聊天记录始终完整保存。**

</div>
</details>

## 📱 功能详解
<details>
<summary>5. 我可以备份微信里的哪些内容？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

目前全面支持：

- ✅ 文字消息（完整保存）
- ✅ 图片（原画质永久存储）
- ✅ 文件附件（PDF、Word、Excel、PPT等）
- 🚧 语音消息（自动转文字，即将全面支持）
- 🚧 视频消息（开发中，敬请期待）

**备份逻辑：** 您选择什么，我们就处理什么。在微信转发时，可自由勾选或排除任意类型的内容。

</div>
</details>

<details>
<summary>6. 可以只备份文字，不备份图片和文件吗？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**完全可以，备份内容由您100%决定。**

**两种备份模式：**

- **纯文字备份**
  - 仅勾选文字消息
  - AI仅基于文字生成摘要
  - 不占用图片/文件存储空间
- **完整上下文备份**
  - 同时勾选文字+相关图片/文件
  - AI会识别图片中的文字和文件内容
  - 生成的摘要包含完整上下文信息

**建议：** 对于重要对话（如合同讨论、地址确认、方案评审），建议采用完整备份，确保AI能提供最准确的分析。

</div>
</details>

<details>
<summary>7. 如何快速找到特定的聊天记录？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

我们的智能搜索和筛选系统能帮您秒速定位所需对话

🔍 **智能搜索框**

- **全文搜索：** 涵盖原始消息、AI摘要及图片中的文字
- **多条件筛选：** 支持按联系人、标签、标题、内容类型精准筛选
- **模糊匹配：** 输入部分信息即可联想相关对话

</div>
</details>

<details>
<summary>8. 在哪里查看我的使用情况和数据统计？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

在 **【订阅与账单】** 页面中，您可以清晰掌握所有用量信息，使每一笔消费都完全透明。

📊 **数据统计**

- **自定义使用周期统计：** 灵活查看最近**1天**、**7天**、**30天或任意时间段**内的对话处理量趋势。
- **订阅情况与权益详情：** 直观展示当前订阅情况及积分使用情况
- **对话积分消耗明细：** 详细列出每条备份的积分消耗，让消费完全透明。

</div>
</details>

<details>
<summary>9. 可以分享备份或与他人协作吗？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**当前支持：**

- **导出为PDF：** 精美排版，可打印或分享
- **API接口** （企业版）：集成到您的OA、CRM系统
- **团队协作功能** （企业版）：共享备份库、协同标注

**即将推出：**

- 加密链接分享（设置密码和有效期）
- 团队空间（小团队协作版）
- 微信小程序查看端

**个人版用户** 目前建议通过PDF导出后分享。

</div>
</details>

## 💳 账户与订阅
<details>
<summary>10. 如何注册与免费试用？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

AImyChats提供两种便捷的注册方式，您可以任选其一快速开始：

- 访问 [aimychats.com](https://app.aimychats.com/login?tab=register)
  -  🌐 **方式一：Google 账号登录**
     - 点击“使用 Google 账号继续”
     - 自定义AI邮箱用户名
     - 完成注册
  -  📧 **方式二：邮箱注册**
     - 输入您的个人或工作邮箱地址
     - 查收系统发送的激活邮件（请务必检查垃圾邮件箱）
     - 点击邮件中的激活链接，完成注册
- 注册成功后，系统会自动为您生成一个 **@aimychats.com** 的专属邮箱

🔑 **重要说明**

- **登录账号：** 使用系统分配的 @aimychats.com 邮箱 和您设置的密码登录平台
- **专属收件箱：** 该 @aimychats.com 邮箱用于接收微信转发的聊天
- **微信发件人：** 您的个人邮箱将作为微信邮件的发送账户

🎁 **新用户福利：**

- 30天免费体验
- 无信用卡要求，注册即用
- 免费体验期间，无任何费用

</div>
</details>

<details>
  <summary>11. 如何选择适合我的版本？</summary>
  <div style="margin:4px 0 12px 0; padding:0; overflow:hidden;">
    <table style="width:100%; border-collapse: collapse; table-layout: auto; font-size: 0.9em; margin:0;">
      <thead>
        <tr style="background:#F9FAFB; border-bottom:1px solid #E5E7EB;">
          <th style="padding:10px 12px; text-align:left; color:#111827;">功能</th>
          <th style="padding:10px 12px; text-align:center; color:#111827;">免费体验</th>
          <th style="padding:10px 12px; text-align:center; color:#111827;">Starter<br><span style="font-weight:400; font-size:0.85em; color:#6B7280;">（个人用户）</span></th>
          <th style="padding:10px 12px; text-align:center; color:#111827;">Standard<br><span style="font-weight:400; font-size:0.85em; color:#6B7280;">（专业用户）</span></th>
          <th style="padding:10px 12px; text-align:center; color:#111827;">Pro<br><span style="font-weight:400; font-size:0.85em; color:#6B7280;">（企业用户）</span></th>
        </tr>
      </thead>
      <tbody>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">价格</td><td style="text-align:center; color:#059669; font-weight:600;">免费</td><td style="text-align:center; font-weight:600;">$4.99/月</td><td style="text-align:center; font-weight:600;">$9.90/月</td><td style="text-align:center; font-weight:600;">$29.9/月</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">存储空间</td><td style="text-align:center;">1 GB</td><td style="text-align:center;">5 GB</td><td style="text-align:center;">10 GB</td><td style="text-align:center;">20 GB</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">对话上限</td><td style="text-align:center;">5组/月</td><td style="text-align:center;">100组/月</td><td style="text-align:center;">500组/月</td><td style="text-align:center;">2,000组/月</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">每组附件图片</td><td style="text-align:center;">5个</td><td style="text-align:center;">10个</td><td style="text-align:center;">15个</td><td style="text-align:center;">25个</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">数据保留</td><td style="text-align:center;">30天</td><td style="text-align:center;">1年</td><td style="text-align:center;">3年</td><td style="text-align:center;">永久保留</td></tr>
        <tr style="background:#F9FAFB; border-bottom:1px solid #F3F4F6;"><td style="padding:8px 12px; font-weight:600; color:#374151;" colspan="5">核心功能</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">✅ 搜索功能</td><td style="text-align:center;">基础</td><td style="text-align:center;">高级</td><td style="text-align:center;">高级</td><td style="text-align:center;">高级</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">✅ 智能分析场景</td><td style="text-align:center;">基础</td><td style="text-align:center;">多场景</td><td style="text-align:center;">多场景</td><td style="text-align:center;">多场景</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">✅ AI图片识别</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">✅ AI智能摘要</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td></tr>
        <tr style="background:#F9FAFB; border-bottom:1px solid #F3F4F6;"><td style="padding:8px 12px; font-weight:600; color:#374151;" colspan="5">高级功能</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">🔍 元数据自动分析</td><td style="text-align:center; color:#E5E7EB;">❌</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">📎 非图片附件保存</td><td style="text-align:center; color:#E5E7EB;">❌</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">🌐 多语言智能分析</td><td style="text-align:center; color:#E5E7EB;">❌</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td><td style="text-align:center;">✅</td></tr>
        <tr style="border-bottom:1px solid #F3F4F6;"><td style="padding:10px 12px;">📧 IMAP邮件自动收取</td><td style="text-align:center; color:#E5E7EB;">❌</td><td style="text-align:center; color:#E5E7EB;">❌</td><td style="text-align:center;"><div style="line-height:1.2;">✅<div style="font-size:0.8em; color:#6B7280; font-weight:normal;">(即将开放)</div></div></td><td style="text-align:center;"><div style="line-height:1.2;">✅<div style="font-size:0.8em; color:#6B7280; font-weight:normal;">(即将开放)</div></div></td></tr>
        <tr><td style="padding:10px 12px;">🔗 智能总结提交JIRA</td><td style="text-align:center; color:#E5E7EB;">❌</td><td style="text-align:center; color:#E5E7EB;">❌</td><td style="text-align:center;"><div style="line-height:1.2;">✅<div style="font-size:0.8em; color:#6B7280; font-weight:normal;">(即将开放)</div></div></td><td style="text-align:center;"><div style="line-height:1.2;">✅<div style="font-size:0.8em; color:#6B7280; font-weight:normal;">(即将开放)</div></div></td></tr>
      </tbody>
    </table>

  </div>

  <p style="margin-top:8px; padding-left: 12px; font-size: 0.85em; color: #6B7280; text-align: left;">所有付费方案均可随时升级或降级，按月计费，随时可取消。</p>
</details>


<details>
<summary>12. 各版本适用哪些场景？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

🆓 **免费版 - 个人试用**
- **适合人群:** 初次体验用户、低频使用者
- **核心价值：** 体验核心功能，轻松管理少量重要对话
- **推荐场景：** 备份少量关键对话、体验AI摘要功能

🏠 **Starter - 个人用户首选**
- **适合人群：** 个人用户、学生、自由职业者
- **核心价值：** 高性价比日常聊天管理
- **推荐场景：** 日常聊天记录管理、随时查阅回顾、支持图片附件

💼 **Standard - 专业人士推荐**
- **适合人群：** 职场人士、中小企业团队、内容创作者
- **核心价值：** 专业级数据处理与长期保存
- **推荐场景：** 工作沟通备份、项目记录管理、团队协作

🏢 **Pro - 企业级解决方案**
- **适合人群：** 企业用户、多团队协作、高频使用者
- **核心价值：** 大量数据处理与永久保存
- **推荐场景：** 企业知识管理、跨部门协作、长期合规存储

</div>
</details>

<details>
<summary>13. 订阅价格与支付方式</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

透明定价，随时取消
**支付方式：**
- 💳 信用卡（Visa、MasterCard、American Express）
- 💰 支付宝
- 💵 微信

**发票服务：**
- 开票流程：设置 → 账单管理 → 申请发票

🎓**教育优惠：**
- 学生及教育工作者可享 **50%折扣**
- 请使用教育邮箱注册并联系我们验证。

</div>
</details>

<details>
<summary>14. 如何升级、降级或取消订阅？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">
随时灵活调整：

**升级计划：**
- 登录后进入"订阅与账单" 
- 选择新计划，立即生效

**降级或取消：**
- 登录后进入"设置" → "订阅管理"
- 点击"更改计划"或"取消订阅"
- 当前周期结束后自动生效

**重要提示：** 降级到免费体验前，请确保数据不超过1GB，否则部分文件将变为只读。

</div>
</details>

<details>
<summary>15. 取消订阅后，我的数据会如何处理？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

- 只保留最近 30 天的数据（旧数据自动删除）
- 您可以在降级前导出数据
- 重新订阅后所有功能立即恢复

我们提供清晰的数据过渡方案：

**取消订阅后：**

- 周期结束：当前付费周期结束后，自动转为免费体验
- 数据调整：
  - 存储数据超过1GB的部分标记为"只读"
  - 仅保留最近30天的备份记录（旧数据自动删除）

**数据安全措施：**
- 降级前随时导出数据
- 重新订阅后，所有功能立即恢复

**我们的承诺：** 即使您选择离开，您的数据始终受控于您。

</div>
</details>

## 🔧 常见问题排查

<details>
<summary>16. 没收到确认邮件或处理失败？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**首先请检查：**

- 📥 垃圾邮件/促销邮件文件夹
- ✉️ 邮箱地址是否正确（注册时填写的邮箱）
- ⏰ 是否刚发送（处理可能需要1-5分钟）

**如果仍未收到：**
- 登录账号，点击"重新发送验证邮件"
- 或联系 support@email.aimychats.com，提供：
  - 您的注册邮箱
  - 大致注册时间
  - 问题描述

</div>
</details>

<details>
<summary>17. 转发邮件后，为什么在平台看不到？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**可能原因及解决方案：**

<div style="margin:4px 0 12px 0; padding:0; overflow:hidden; overflow-x:auto;">
  <table style="width:100%; border-collapse: collapse; table-layout: auto; font-size: 0.9em; margin:0;">
    <thead>
      <tr style="background:#F9FAFB; border-bottom:1px solid #E5E7EB;">
        <th style="padding:10px 12px; text-align:left; color:#111827;">问题现象</th>
        <th style="padding:10px 12px; text-align:left; color:#111827;">可能原因</th>
        <th style="padding:10px 12px; text-align:left; color:#111827;">解决方案</th>
      </tr>
    </thead>
    <tbody>
      <tr style="border-bottom:1px solid #F3F4F6;">
        <td style="padding:10px 12px; font-weight:600; color:#374151;">完全无记录</td>
        <td style="padding:10px 12px;">1. 使用错误的专属地址<br/>2. 邮件仍在队列中<br/>3. 附件格式不支持</td>
        <td style="padding:10px 12px;">1. 确认复制正确的地址<br/>2. 等待5-10分钟<br/>3. 检查文件是否损坏</td>
      </tr>
      <tr style="border-bottom:1px solid #F3F4F6;">
        <td style="padding:10px 12px; font-weight:600; color:#374151;">有记录但无摘要</td>
        <td style="padding:10px 12px;">1. 内容过短<br/>2. 非中文/英文内容<br/>3. 系统临时繁忙</td>
        <td style="padding:10px 12px;">1. 尝试重新生成摘要<br/>2. 或手动添加摘要<br/>3. 稍后再试</td>
      </tr>
      <tr>
        <td style="padding:10px 12px; font-weight:600; color:#374151;">图片/附件缺失</td>
        <td style="padding:10px 12px;">1. 文件过大（超过计划限制）<br/>2. 不支持的文件类型<br/>3. 上传中</td>
        <td style="padding:10px 12px;">1. 检查订阅计划限制<br/>2. 查看支持的文件列表<br/>3. 等待上传完成</td>
      </tr>
    </tbody>
  </table>
</div>

**技术支持**：如果问题持续，请提交工单并附上邮件发送截图。

</div>
</details>

<details>
<summary>18. 图片显示异常或无法加载？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**快速排查步骤：**
- **刷新页面：** 可能只是临时加载问题
- **检查网络：** 切换到稳定的Wi-Fi环境
- **查看存储状态：**
  - 登录后存储使用情况
  - 免费体验用户可能已超过1GB限制

**永久解决方案：**
- 升级到更高存储容量的计划
- 清理不需要的备份
- 联系技术支持排查账户问题

</div>
</details>

<details>
<summary>19. 如何导出我的数据？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

- 数据导出功能即将推出，敬请期待！

</div>
</details>

## ⚖️ 隐私与法律
<details>
<summary>20. 数据存储在哪里？谁能查看？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**数据存储位置：**
- 中国用户：阿里云（中国区）
- 国际用户：AWS（美国/欧洲）
- 注册时可选择偏好的存储区域
 
**数据访问权限：**
- 🔒 **默认情况：** 只有您本人可以访问
- 👁️ **例外情况：** 
  - 您主动联系技术支持并明确授权
  - 法律要求（我们会提前通知您，除非法律禁止）


**隐私保护承诺：**
- 我们绝不售卖或分享您的个人数据
- 严格遵守隐私政策。[隐私政策](/zh/privacy.md)

</div>
</details>

<details>
<summary>21. 是否符合GDPR等数据保护法规？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**完全符合，** 并为您提供完整的权利保障：

**您的权利：**

- ✅ **访问权：** 随时访问自己的所有数据
- ✅ **删除权：** 随时删除自己的所有数据
- ✅ **携带权：** 随时导出自己的数据
- ✅ **更正权：** 可更正不准确或不完整的个人数据
- ✅ **反对权：** 可反对某些数据处理方式

</div>
</details>

## 🛟 获取帮助
<details>
<summary>22. 如何获得技术支持？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**邮件支持：** support@email.aimychats.com

**工作时间：** 周一至周五 9:00-18:00（中国时间）

**响应时间：**
- 免费体验版：72小时内
- Starter个人用户：48小时内
- Standard专业用户：24小时内
- Pro企业用户：专属技术支持（4小时内）

</div>
</details>

<details>
<summary>23. 提交工单需要哪些信息？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">

**请提供：**

- 您的账号邮箱
- 问题描述
- 复现步骤
- 截图（如有）
- 发生时间

</div>
</details>

<details>
<summary>24. 有用户社区或更多学习资源吗？</summary>
<div style="margin:12px 0; padding-left:12px; border-left:3px solid #F3F4F6;">
即将推出！敬请期待。

</div>
</details>

---
<br>

<small>[返回顶部 ↑](#top)</small> 