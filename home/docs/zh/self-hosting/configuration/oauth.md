# OAuth 登录

Google OAuth 登录是可选的。配置后，用户除了用户名/密码，还可以用 Google 登录。

## 配置 Google OAuth

在环境文件中设置：

| 变量 | 用途 |
|------|------|
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret |
| `ACCOUNT_DEFAULT_HTTP_PROTOCOL` | 开发 `http`，生产 `https` |

`SITE_DOMAIN` 必须与你在 Google Cloud OAuth 凭据里登记的授权重定向来源域名一致。

## 首次登录

首次 OAuth 登录时，用户会完成一次简短的账户绑定，把外部 Google 身份关联到其 Devify 账户。
