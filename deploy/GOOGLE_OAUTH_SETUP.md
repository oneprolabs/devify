# Google OAuth 配置指南（生产环境）

## 问题诊断

**错误信息：** `Error 400: redirect_uri_mismatch`

**原因：** Google Cloud Console 中配置的回调 URI 与应用实际发送的不匹配。

---

## ⚡ 快速诊断清单

遇到 `redirect_uri_mismatch` 错误时，按顺序检查：

### 1️⃣ 检查 Django Site 配置
```bash
docker exec devify-api python manage.py shell -c "
from django.contrib.sites.models import Site
print(Site.objects.get_current().domain)
"
```
✅ 应该输出：`app.aimychats.com`（或你的实际域名）

### 2️⃣ 检查实际发送的 redirect_uri
浏览器访问 OAuth 登录，在开发者工具的 Network 标签中查看跳转 URL：
- ✅ 协议应该是 `https://`（不是 `http://`）
- ✅ 域名应该与 SITE_DOMAIN 一致
- ✅ 路径应该是 `/accounts/google/login/callback/`

### 3️⃣ 检查 OAuth 协议配置（CRITICAL）
```bash
docker exec devify-api python manage.py shell -c "
from django.conf import settings
print(settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL)
"
```
- ✅ 生产环境应该输出：`https`
- ❌ 如果输出 `http` 或报错，需要在 .env 中添加：`ACCOUNT_DEFAULT_HTTP_PROTOCOL=https`

### 4️⃣ 检查反向代理配置（使用 NPM 时必查）
```bash
docker exec devify-api python manage.py shell -c "
from django.conf import settings
print(settings.SECURE_PROXY_SSL_HEADER)
"
```
- ✅ 应该输出：`('HTTP_X_FORWARDED_PROTO', 'https')`
- ❌ 如果输出 `None`，参见下面的 "使用 Nginx Proxy Manager 的特殊配置" 部分

### 5️⃣ 检查 Google Console 配置
确保在 Google Cloud Console 的 "Authorized redirect URIs" 中添加了完整的回调 URI：
```
https://app.aimychats.com/accounts/google/login/callback/
```

---

## 解决步骤

### 1. 确认你的生产环境域名

根据你的配置，应该使用：

- **域名：** `app.aimychats.com`
- **协议：** `https://` （生产环境必须使用 HTTPS）
- **回调 URI：** `https://app.aimychats.com/accounts/google/login/callback/`

### 2. 在 Google Cloud Console 中配置回调 URI

1. **访问 Google Cloud Console**
   - 打开：https://console.cloud.google.com/
   - 选择你的项目

2. **导航到 OAuth 配置**
   - 左侧菜单：**API 和服务** → **凭据**
   - 找到你的 OAuth 2.0 客户端 ID（Web 应用类型）

3. **添加授权的重定向 URI**

   在 **授权的重定向 URI** 部分，添加：
   ```
   https://app.aimychats.com/accounts/google/login/callback/
   ```

   **重要注意事项：**
   - ✅ 必须使用 `https://`（生产环境）
   - ✅ 必须包含完整域名 `app.aimychats.com`
   - ✅ 路径必须是 `/accounts/google/login/callback/`
   - ✅ 结尾必须有斜杠 `/`
   - ❌ 不要使用 IP 地址（Google 不允许私有 IP）
   - ❌ 不要添加端口号（HTTPS 默认 443）

4. **保存配置**
   - 点击 **保存** 按钮
   - 等待几秒钟让配置生效

### 3. 验证 .env 配置

确保你的 `devify-deploy/.env` 文件包含正确的配置：

```bash
# Django Site Configuration (Required for OAuth)
SITE_DOMAIN=app.aimychats.com
SITE_NAME=AImyChats

# Google OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID=your_actual_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_actual_client_secret

# OAuth Protocol Configuration (CRITICAL for HTTPS)
# This ensures django-allauth generates https:// callback URLs
ACCOUNT_DEFAULT_HTTP_PROTOCOL=https

# Frontend URL (for OAuth redirects)
FRONTEND_URL=https://app.aimychats.com

# Frontend API Base URL
VITE_API_BASE_URL=https://app.aimychats.com

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS='https://app.aimychats.com'
```

### 4. 重启服务（如果修改了 .env）

如果你修改了 `.env` 文件中的配置，需要重启容器：

```bash
cd /home/ubuntu/workspace/devify_workspace/devify-deploy
./scripts/devify-deploy.sh restart devify-api devify-worker
```

### 5. 验证配置是否生效

运行以下命令检查 Django 中的 Site 配置：

```bash
docker exec devify-api python manage.py shell -c "
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
site = Site.objects.get_current()
print(f'Site Domain: {site.domain}')
print(f'Site Name: {site.name}')
try:
    google_app = SocialApp.objects.get(provider='google')
    print(f'Google OAuth Client ID: {google_app.client_id[:30]}...')
    print(f'Google OAuth configured: Yes')
except SocialApp.DoesNotExist:
    print('Google OAuth configured: No')
"
```

**预期输出：**
```
Site Domain: app.aimychats.com
Site Name: AImyChats
Google OAuth Client ID: your_client_id...
Google OAuth configured: Yes
```

## 使用 Nginx Proxy Manager 的特殊配置（重要）

如果你使用 **Nginx Proxy Manager**（NPM）作为外部反向代理，需要额外配置以确保 Django 能正确识别 HTTPS 协议。

### 问题症状

即使 Google Console 配置了 `https://` 回调 URI，OAuth 跳转时仍然使用 `http://`，导致 `redirect_uri_mismatch` 错误。

### 解决方案

#### 步骤 1：配置 Nginx Proxy Manager

在 NPM 管理界面中：

1. 找到 `app.aimychats.com` 的代理主机配置
2. 进入 **"Custom Nginx Configuration"** 或 **"Advanced"** 标签
3. 添加以下配置：

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
```

**关键配置：** `proxy_set_header X-Forwarded-Proto $scheme;` 这行会告诉 Django 原始请求使用的是 HTTPS 协议。

4. 保存配置

#### 步骤 2：验证 Django 配置

Django 代码中已包含以下配置（位于 `devify/core/settings/base.py`）：

```python
# Trust proxy headers from nginx
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

验证是否生效：

```bash
docker exec devify-api python manage.py shell -c "
from django.conf import settings
print('SECURE_PROXY_SSL_HEADER:', settings.SECURE_PROXY_SSL_HEADER)
print('USE_X_FORWARDED_HOST:', settings.USE_X_FORWARDED_HOST)
"
```

**预期输出：**
```
SECURE_PROXY_SSL_HEADER: ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST: True
```

如果输出为 `None`，说明代码未更新，需要重新部署应用。

#### 步骤 3：重启服务

```bash
cd /root/devify-deploy
./scripts/devify-deploy.sh restart devify-api devify-worker
```

#### 步骤 4：验证 OAuth URL

访问 `https://app.aimychats.com/auth`，点击 Google 登录，在浏览器开发者工具的 Network 标签中检查跳转 URL：

```
https://accounts.google.com/o/oauth2/v2/auth?...&redirect_uri=https%3A%2F%2Fapp.aimychats.com%2Faccounts%2Fgoogle%2Flogin%2Fcallback%2F
```

**重点检查：** `redirect_uri` 参数应该是 `https://`（而不是 `http://`）

---

## 常见问题排查

### 问题 1：修改后仍然报错

**解决方案：**
1. 清除浏览器缓存和 Cookie
2. 等待 1-2 分钟让 Google 配置生效
3. 尝试使用无痕模式测试

### 问题 2：SITE_DOMAIN 配置不正确

**检查方法：**
```bash
docker exec devify-api python manage.py shell -c "
from django.contrib.sites.models import Site
print(Site.objects.get_current().domain)
"
```

**如果输出不正确，手动更新：**
```bash
docker exec devify-api python manage.py shell -c "
from django.contrib.sites.models import Site
site = Site.objects.get_current()
site.domain = 'app.aimychats.com'
site.name = 'AImyChats'
site.save()
print('Site updated successfully')
"
```

### 问题 3：Google OAuth 应用未初始化

**手动初始化：**
```bash
docker exec devify-api python manage.py init_social_apps
```

### 问题 4：redirect_uri 使用 http 而不是 https（常见）

**症状：** 即使在 Google Console 配置了 `https://` 回调 URI，实际跳转时使用的是 `http://`

**原因：** 反向代理（如 Nginx Proxy Manager）没有正确传递协议信息给 Django

**解决方案：** 参见上面的 **"使用 Nginx Proxy Manager 的特殊配置"** 部分

**快速检查：**
```bash
# 1. 检查 Django 配置
docker exec devify-api python manage.py shell -c "
from django.conf import settings
print(settings.SECURE_PROXY_SSL_HEADER)
"

# 如果输出 None，需要更新代码并重启
```

### 问题 5：使用多个域名

如果你需要支持多个域名（例如测试环境和生产环境），需要在 Google Cloud Console 中添加所有回调 URI：

```
https://app.aimychats.com/accounts/google/login/callback/
https://test.aimychats.com/accounts/google/login/callback/
https://192.168.8.182:10443/accounts/google/login/callback/
```

**注意：** Google 不允许使用私有 IP 地址（如 192.168.x.x），只能用于本地测试。

## 测试 OAuth 流程

1. **访问登录页面：**
   ```
   https://app.aimychats.com/auth
   ```

2. **点击 "Sign in with Google" 按钮**

3. **检查重定向 URL：**
   - 应该跳转到 Google 登录页面
   - URL 中应包含 `redirect_uri=https://app.aimychats.com/accounts/google/login/callback/`

4. **成功登录后：**
   - 应该重定向回你的应用
   - 自动跳转到 `/auth/oauth/callback` 页面

## 架构说明：为什么需要配置反向代理

### 典型的生产环境架构

```
用户浏览器 (HTTPS)
    ↓
Nginx Proxy Manager (443) ← 在这里终止 SSL
    ↓ (HTTP)
Docker 内部 Django (8000)
```

### 问题根源

1. **用户通过 HTTPS 访问** `https://app.aimychats.com`
2. **Nginx Proxy Manager 终止 SSL**，将请求转发给后端（通过 HTTP）
3. **Django 只看到 HTTP 请求**，不知道原始请求是 HTTPS
4. **Django 生成回调 URL** 时使用 `http://` 协议
5. **Google 拒绝**，因为你在 Console 中配置的是 `https://`

### 解决方案原理

通过配置反向代理头：

```nginx
proxy_set_header X-Forwarded-Proto $scheme;  # 告诉 Django："原始协议是 HTTPS"
```

配合 Django 设置：

```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Django："我信任这个头"
```

这样 Django 就能正确生成 `https://` 的回调 URL 了。

### 安全注意事项

**为什么需要 `SECURE_PROXY_SSL_HEADER`？**

- Django 默认不信任 `X-Forwarded-Proto` 头，因为恶意用户可能伪造这个头
- 只有在确认有可信的反向代理时，才应该启用这个配置
- 在生产环境中，确保只有受信任的代理（如 NPM）能访问 Django 服务端口

---

## 参考资料

- Google OAuth 2.0 文档：https://developers.google.com/identity/protocols/oauth2
- Django Allauth 文档：https://docs.allauth.org/
- Django SECURE_PROXY_SSL_HEADER 文档：https://docs.djangoproject.com/en/stable/ref/settings/#secure-proxy-ssl-header
- 项目 README：`../devify/README.md`

## 需要帮助？

如果问题仍然存在，请提供：
1. 你的实际域名
2. Google Cloud Console 中配置的回调 URI 截图
3. `.env` 文件中的 `SITE_DOMAIN` 配置（脱敏后）
4. 执行验证命令的输出
5. 浏览器 Network 标签中实际的 OAuth 跳转 URL
