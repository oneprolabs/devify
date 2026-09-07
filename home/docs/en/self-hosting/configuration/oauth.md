# OAuth Login

Google OAuth login is optional. When configured, users can sign in with Google
in addition to username / password.

## Configure Google OAuth

Set the following in your env file:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret |
| `ACCOUNT_DEFAULT_HTTP_PROTOCOL` | `http` for dev, `https` for production |

`SITE_DOMAIN` must match the public domain registered as an authorized redirect
origin in your Google Cloud OAuth credentials.

## First sign-in

On first OAuth sign-in, the user completes a short account-binding step that
links the external Google identity to their Devify account.
