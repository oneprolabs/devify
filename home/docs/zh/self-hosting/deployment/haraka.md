# 入站邮件（Haraka）

Devify 内置 [Haraka](https://haraka.github.io/)，让用户可以在自动分配的地址收信：

```text
{用户名}@{AUTO_ASSIGN_EMAIL_DOMAIN}
```

Haraka 监听 SMTP 25 端口，把原始邮件写入 `data/haraka/emails`，worker/scheduler 再将其接入正常的邮件处理流程。

## 配置邮件域名

生产环境需在**三处**配置邮件域名：

1. `.env`：`AUTO_ASSIGN_EMAIL_DOMAIN=example.com`
2. `docker/haraka/config/host_list.prod`：加入 `example.com`
3. DNS：为 `example.com` 添加指向 Haraka 主机的 **MX** 记录。

## 推荐 DNS 记录

```text
example.com.        MX   10 mail.example.com.
mail.example.com.   A    <服务器公网IP>
example.com.        TXT  "v=spf1 mx -all"
_dmarc.example.com. TXT  "v=DMARC1; p=quarantine; rua=mailto:admin@example.com"
```

25 端口必须可从公网访问。

## STARTTLS

```bash
HARAKA_DOMAIN=mail.example.com HARAKA_CERT_EMAIL=admin@example.com \
  ./scripts/manage-haraka-certs.sh apply
```

详见 [`docker/haraka/README.md`](https://github.com/cloud2ai/devify/blob/main/docker/haraka/README.md)。
