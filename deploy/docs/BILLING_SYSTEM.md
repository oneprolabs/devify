# 计费系统 - 订阅管理与积分续期

## 系统概览

计费系统通过定时任务自动管理 Free Plan 和 Paid Plan 用户的积分和订阅状态，确保：

1. **积分自动续期**：周期到期时自动重置积分
2. **支付处理**：Stripe webhook 实时处理支付
3. **自动降级**：支付失败自动降级到 Free Plan
4. **用户永不锁定**：确保用户始终可以使用系统

## 核心设计理念：用户永不锁定

**设计哲学**：用户不会因为不付费而被完全锁定在系统之外。

- ✅ Free Plan 用户：每 30 天自动续期 10 个积分
- ✅ Paid Plan 用户：只要支付，就能享受付费权益
- ✅ **支付失败**：7 天宽限期，之后自动降级到 Free Plan
- ✅ **不付费**：用户继续使用 Free Plan（有限功能）

**结果**：优秀的用户体验 + 自然的付费转化漏斗

## 自动任务调度

### Celery Beat 定时任务

| 任务 | 执行时间 | 功能 | 适用范围 |
|------|---------|------|---------|
| `renew_expired_credits` | 每天 04:00 | 刷新过期积分 | Free + Paid |
| `downgrade_failed_paid_subscriptions` | 每天 05:00 | 降级失败的付费订阅 | Paid Plan 专用 |

## Free Plan 用户流程

### 注册时初始化

```
用户完成注册
  ↓
自动创建 Free Plan 订阅：
  - plan: Free Plan
  - status: 'active'
  - auto_renew: False
  - period: 30 天
  ↓
初始化积分：
  - base_credits: 10
  - consumed_credits: 0
  - period: 11/12 - 12/12
  ↓
✅ 用户获得 10 个免费积分
```

### 周期到期后自动续期

```
Day 30 (12/12): 周期到期
  ↓
积分可能已用完或有剩余
  ↓
次日凌晨 04:00
  ↓
【Celery 定时任务: renew_expired_credits】
  ↓
检测条件：
  - period_end <= now ✅
  - is_active = True ✅
  - subscription.status = 'active' ✅
  ↓
执行重置：
  - consumed_credits: 8 → 0
  - base_credits: 10 → 10
  - period_start: 12/13
  - period_end: 01/12
  ↓
✅ 用户再次获得 10 个积分！
```

**关键点：**
- 🔄 **完全自动**：无需用户任何操作
- 🔄 **无需支付**：Free Plan 永久免费
- 🔄 **永久有效**：只要 subscription 是 'active'

## Paid Plan 用户流程

### 升级订阅（实时处理）

```
用户在界面点击"升级到 Starter"
  ↓
前端调用: createCheckoutSession(price_id)
  ↓
后端创建 Stripe Checkout Session
  ↓
用户跳转到 Stripe 支付页面
  ↓
输入信用卡信息并支付
  ↓
✅ 支付成功（实时，秒级）
  ↓
【Stripe Webhook: customer.subscription.created】
  ↓
后端处理:
  1. 取消旧的 Free Plan
  2. 创建新的 Starter Plan
  3. 更新积分: 10 → 100
  4. 更新周期
  ↓
✅ 立即生效！用户刷新页面就看到 100 积分
```

**处理时机：** ⚡ **实时**（Webhook，秒级响应）

### 续费成功（实时 + 定时）

```
Day 30: Stripe 自动扣款
  ↓
✅ 扣款成功
  ↓
【Stripe Webhook: invoice.payment_succeeded】（实时）
  ↓
  - 如果之前是 'past_due' → 恢复为 'active'
  - 发送成功通知邮件
  ↓
【Stripe Webhook: customer.subscription.updated】（实时）
  ↓
sync_from_djstripe():
  - 更新订阅周期：current_period_end = now + 30天
  ↓
次日凌晨 04:00
  ↓
【Celery: renew_expired_credits】
  ↓
  - consumed_credits: 95 → 0
  - base_credits: 100 → 100
  - period: 新的 30 天
  ↓
✅ 用户获得新周期的 100 积分
```

**处理时机：**
- Webhook（实时）：更新订阅状态和周期
- Celery（次日凌晨）：重置积分计数

**为什么分两步？**
- Webhook：避免超时，只做轻量级更新
- Celery：批量处理，统一积分重置逻辑

### 续费失败（实时通知 + 延迟降级）

```
Day 30: Stripe 自动扣款
  ↓
❌ 扣款失败（卡过期、余额不足等）
  ↓
【Stripe Webhook: invoice.payment_failed】（实时）
  ↓
handle_payment_failed():
  - subscription.status = 'past_due'
  - 发送失败通知邮件
  - 提示更新支付方式
  ↓
========== 7 天宽限期 ==========
用户可以：
  - 在 Stripe Customer Portal 更新支付方式
  - 继续使用剩余积分
  - Stripe 会自动重试扣款
  ↓
如果用户更新了支付方式 → Stripe 重试成功 → 恢复 'active' ✅

如果用户仍未支付 → 继续 'past_due'
  ↓
Day 37 凌晨 05:00
  ↓
【Celery: downgrade_failed_paid_subscriptions】
  ↓
检测条件：
  - status = 'past_due'
  - updated_at < (now - 7天)
  - plan 是付费计划
  ↓
执行降级：
  1. 取消旧订阅: status='canceled'
  2. 创建 Free Plan 订阅
  3. 重置积分: 100 → 10
  4. 更新周期: 30 天
  ↓
✅ 用户降级到 Free Plan
   - 失去付费权益（100 credits → 10 credits）
   - 可继续使用（免费版功能）
   - 随时可以重新订阅
```

**处理时机：**
- 失败通知：⚡ **实时**（Webhook）
- 自动降级：🕐 **7天后**（Celery，宽限期）

**为什么延迟降级？**
- 给用户时间解决支付问题
- 避免误伤（临时卡问题）
- 更好的用户体验

## 关键技术实现

### Webhook vs Celery 的分工

| 处理方式 | 时机 | 用途 | 优势 |
|---------|------|------|------|
| **Stripe Webhook** | 实时（秒级） | 支付状态变更、订阅创建/更新 | 即时响应 |
| **Celery Beat** | 定时（每日） | 批量积分刷新、降级处理 | 统一逻辑、可靠性高 |

### 为什么积分刷新用 Celery 而不是 Webhook？

1. **统一处理**：Free Plan 和 Paid Plan 用同一套逻辑
2. **避免超时**：Webhook 要求快速响应（< 5秒）
3. **批量处理**：一次性处理所有到期用户，效率高
4. **可靠性**：即使 Webhook 遗漏，定时任务也能兜底

## 监控与维护

### 检查定时任务运行状态

```bash
# 查看 Celery Beat 调度
docker exec devify-scheduler celery -A core inspect scheduled

# 查看任务执行日志
docker logs devify-scheduler | grep "renew_expired_credits"
docker logs devify-scheduler | grep "downgrade_failed"

# 查看具体用户积分
docker exec devify-api python manage.py shell -c "
from accounts.models import User
from billing.models import UserCredits
u = User.objects.get(username='john')
c = UserCredits.objects.get(user=u)
print(f'积分: {c.available_credits}/{c.total_credits}')
print(f'周期: {c.period_start} - {c.period_end}')
print(f'订阅: {c.subscription.plan.name if c.subscription else \"无\"}')"
```

### 手动触发任务（测试用）

```bash
# 手动重置单个用户积分
docker exec devify-api python manage.py reset_user_credits --username john

# 手动重置所有用户积分
docker exec devify-api python manage.py reset_user_credits --all

# 手动触发降级任务
docker exec devify-scheduler python -c "
from billing.tasks import downgrade_failed_paid_subscriptions
result = downgrade_failed_paid_subscriptions()
print(result)
"
```

## 故障排查

### 问题：用户积分没有自动续期

**检查步骤：**

1. 确认 Celery Beat 运行：
   ```bash
   docker ps | grep scheduler
   ```

2. 查看定时任务日志：
   ```bash
   docker logs devify-scheduler | tail -100
   ```

3. 检查订阅状态：
   ```sql
   SELECT user_id, status, current_period_end
   FROM billing_subscription
   WHERE user_id = <user_id>;
   ```

4. 检查积分记录：
   ```sql
   SELECT user_id, period_end, subscription_id, is_active
   FROM billing_user_credits
   WHERE user_id = <user_id>;
   ```

5. 手动触发续期测试：
   ```bash
   docker exec devify-api python manage.py reset_user_credits --username john
   ```

### 问题：新注册用户没有订阅

**检查步骤：**

1. 确认 BILLING_ENABLED=true
2. 确认 Free Plan 存在：
   ```bash
   docker exec devify-api python manage.py init_billing_stripe
   ```

3. 手动为用户创建订阅：
   ```bash
   docker exec devify-api python manage.py shell -c "
   from accounts.services.registration import RegistrationService
   from accounts.models import User
   u = User.objects.get(username='john')
   RegistrationService._initialize_free_plan(u)
   "
   ```

## 配置说明

### 环境变量

```bash
# 启用计费系统
BILLING_ENABLED=true

# Stripe 配置
STRIPE_TEST_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# 默认免费积分（billing 禁用时使用）
DEFAULT_FREE_CREDITS=10
```

### 套餐配置

套餐定义在 `conf/billing/plans.yaml`：

```yaml
plans:
  - name: Free Plan
    slug: free
    monthly_price_cents: 0
    metadata:
      credits_per_period: 10    # 每周期 10 个积分
      period_days: 30           # 周期 30 天
      chat_limit: 5             # 最多 5 个聊天
      attachment_limit: 5       # 每封最多 5 个附件
      storage_quota_gb: 1       # 1 GB 存储
      data_retention_days: 30   # 30 天保留期

  - name: Starter Plan
    slug: starter
    monthly_price_cents: 499    # $4.99
    metadata:
      credits_per_period: 100
      period_days: 30
      chat_limit: 100
      # ... 其他配置
```

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                   用户操作（前端）                            │
│                                                              │
│  升级订阅 → Stripe Checkout → 支付 → Webhook（实时）        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                 Stripe Webhooks（实时处理）                  │
│                                                              │
│  • customer.subscription.created → 创建订阅                 │
│  • customer.subscription.updated → 更新订阅                 │
│  • invoice.payment_succeeded → 支付成功                     │
│  • invoice.payment_failed → 支付失败（标记 past_due）       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│              Celery Beat 定时任务（每日处理）                │
│                                                              │
│  04:00 - renew_expired_credits                              │
│    ↓ 检查所有过期的 UserCredits                             │
│    ↓ 如果 subscription.status='active'                      │
│    ↓ 重置积分：consumed=0, base=plan配置, 新周期            │
│                                                              │
│  05:00 - downgrade_failed_paid_subscriptions                │
│    ↓ 检查 past_due > 7天 的付费订阅                         │
│    ↓ 取消付费订阅                                           │
│    ↓ 创建 Free Plan 订阅                                    │
│    ↓ 重置积分到免费额度                                     │
└─────────────────────────────────────────────────────────────┘
```

## 完整用户旅程示例

### 场景 1：Free Plan 用户（永久免费）

```
Day 0: 注册
  → 获得 Free Plan (10 credits)

Day 1-30: 使用系统
  → 处理了 8 封邮件（消耗 8 credits）
  → 剩余 2 credits

Day 30: 周期结束

Day 31 凌晨 04:00: 自动续期
  → consumed: 8 → 0
  → base: 10 → 10
  → ✅ 再次获得 10 credits

永远循环...用户可以无限期免费使用（受限于 Free Plan 配额）
```

### 场景 2：升级到 Starter Plan（实时生效）

```
Day 5: 用户觉得 Free Plan 不够用，点击"升级"
  ↓
跳转到 Stripe 支付页面
  ↓
支付 $4.99（实时，秒级）
  ↓
【Webhook: subscription.created】
  ↓
  - 取消 Free Plan
  - 创建 Starter Plan
  - credits: 10 → 100
  ↓
✅ 刷新页面立即看到 100 credits

Day 35 (订阅后 30 天): Stripe 自动续费
  ↓
✅ 扣款成功
  ↓
【Webhook: payment_succeeded】（实时）
  ↓
次日 04:00【Celery】
  ↓
  - consumed: 0
  - base: 100
  ↓
✅ 持续享受 Starter Plan 权益
```

### 场景 3：支付失败后自动降级（宽限期）

```
Day 65: Stripe 第二次续费尝试
  ↓
❌ 扣款失败（卡过期）
  ↓
【Webhook: payment_failed】（实时）
  ↓
  - status: 'active' → 'past_due'
  - 发送邮件：提醒更新支付方式
  ↓
========== 7 天宽限期 ==========
Day 66-72:
  - 用户收到多次提醒邮件
  - 可以在 Stripe Portal 更新卡信息
  - Stripe 自动重试扣款
  - 用户仍可使用剩余积分
  ↓
Day 72 凌晨 05:00
  ↓
【Celery: downgrade_failed_paid_subscriptions】
  ↓
检测：
  - status='past_due' ✅
  - updated_at < (now - 7天) ✅
  ↓
执行降级：
  1. 取消 Starter Plan (status='canceled')
  2. 创建 Free Plan (status='active')
  3. credits: 100 → 10
  4. 周期: 重新开始 30 天
  ↓
✅ 用户降级到 Free Plan
   - 不会被锁定
   - 继续使用免费版
   - 随时可以重新订阅
```

## 最佳实践

### 1. 监控 Webhook 处理

确保 Stripe Webhooks 正常工作：

```bash
# 查看 webhook 日志
docker logs devify-api | grep WEBHOOK

# 测试 webhook endpoint
curl -X POST https://app.aimychats.com/api/webhooks/stripe/ \
  -H "Stripe-Signature: xxx"
```

### 2. 定期检查定时任务

```bash
# 每周检查一次
docker exec devify-scheduler celery -A core inspect scheduled

# 确认任务执行记录
docker logs devify-scheduler | grep "Credit renewal completed"
```

### 3. 用户支付失败的响应流程

**自动化：**
- ✅ Webhook 自动标记 past_due
- ✅ 自动发送提醒邮件
- ✅ 7 天后自动降级

**人工干预（可选）：**
- 客服联系用户
- 提供优惠码挽留
- 手动延长宽限期

### 4. 数据一致性保障

**订阅与积分的关系：**
- UserCredits.subscription → 必须指向有效的 Subscription
- Subscription.status → 影响积分续期
- 定时任务 → 确保数据最终一致性

## 常见问题

### Q: Free Plan 会过期吗？

**A**: 不会！只要 subscription.status='active'，积分会每 30 天自动续期。

### Q: 用户升级后，旧的积分会保留吗？

**A**: 不会。升级时会立即重置积分到新套餐的配额。例如：
- Free Plan (2/10 剩余) → 升级 → Starter Plan (100/100)

### Q: 降级后，用户之前消耗的积分会恢复吗？

**A**: 不会。降级时重新计算，给予 Free Plan 的初始积分（10个）。

### Q: 支付失败但宽限期内支付成功，积分怎么算？

**A**:
- 支付成功 → status: 'past_due' → 'active'
- 周期继续（不重新开始）
- 积分不变（按原周期结束时重置）

### Q: 可以手动给用户延长宽限期吗？

**A**: 可以。在数据库中更新 subscription.updated_at 即可：

```python
subscription.updated_at = timezone.now()
subscription.save()
# 这会重新开始 7 天倒计时
```

## 总结

**升级**：✅ **实时处理**（Webhook，秒级）
**续费**：✅ **实时通知** + **次日刷新积分**（Webhook + Celery）
**降级**：✅ **7天宽限期** + **自动降级**（Celery）

这种设计平衡了：
- ⚡ **实时性**：支付立即生效
- 🛡️ **可靠性**：定时任务兜底
- 😊 **用户体验**：永不锁定，平滑降级
