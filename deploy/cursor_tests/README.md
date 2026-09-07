# Cursor Browser E2E Test System

## Overview

End-to-end test system using Cursor's built-in browser tools for the Devify billing system.
All tests run against http://localhost:8000 with database operations executed in the `devify-api-dev` container.

## Features

- **No External Dependencies**: Uses Cursor's native browser tools only
- **Fixed Test Users**: Each scenario has a fixed username for consistency
- **Auto Cleanup**: Automatically removes old test data before each run
- **Container-based**: All Python scripts run inside Docker container
- **Markdown Reports**: Test results saved as formatted Markdown with screenshots
- **Modular Design**: Easy to add new test scenarios for different modules
- **Multi-language Support**: Payment notifications support English, Chinese, Spanish via Django i18n

## Quick Start

### 1. Read Documentation

**Environment Setup:**
```bash
cat .cursor_tests/SETUP.md
```

**Stripe Payment Guide:**
```bash
cat .cursor_tests/STRIPE_OPERATIONS.md
```

These explain the environment prerequisites, Stripe test cards, and troubleshooting.

### 2. Execute Test Scenarios

**✅ Recommended: Using Cursor AI with Built-in Browser**

In Cursor, simply say:

```
"Use built-in browser to run all @scenarios tests"
```

Or test specific scenarios:

```
"Execute scenario 1 test"
"Run billing_03_downgrade scenario"
"Test @billing_01_subscribe using browser"
```

Cursor AI will automatically:
- Create test users
- Use built-in browser to execute all steps
- Verify database state
- Report test results

**Manual Execution**

Follow the steps in the scenario file manually, copying commands to terminal.

## Test Scenarios

### Billing Module

| Scenario | File | Description |
|----------|------|-------------|
| 0 | `billing_00_free_plan.md` | Free Plan initial state for new users |
| 1 | `billing_01_subscribe.md` | Subscribe from Free to Standard/Pro |
| 2 | `billing_02_upgrade.md` | Upgrade from Starter to Pro (immediate) |
| 3 | `billing_03_downgrade.md` | Downgrade from Pro to Standard (period end) |
| 4 | `billing_04_cancel.md` | Cancel subscription (remains until period end) |
| 5 | `billing_05_resume.md` | Resume canceled subscription |
| 6 | `billing_06_upgrade_canceled.md` | Upgrade when subscription is canceled |
| 7 | `billing_07_edge_case_downgrade_then_cancel.md` | Edge case: Downgrade then cancel |
| 8 | `billing_08_payment_failed.md` | Payment failure on auto-renewal |
| 9 | `billing_09_payment_recovered.md` | Payment recovery (past_due → active) |

### Future Modules (Extensible)

You can add more scenarios for other modules:
- `threadline_*.md` - Workflow and email processing tests
- `account_*.md` - User registration and authentication tests
- `email_*.md` - Email handling tests

## Directory Structure

```
.cursor_tests/
├── SETUP.md                      # Environment setup guide
├── scenarios/                    # Test scenario definitions
│   ├── billing_00_free_plan.md
│   ├── billing_01_subscribe.md
│   ├── billing_02_upgrade.md
│   ├── billing_03_downgrade.md
│   ├── billing_04_cancel.md
│   ├── billing_05_resume.md
│   └── billing_06_upgrade_canceled.md
├── helpers/                      # Python helper scripts
│   ├── setup_test_user.py       # Create/cleanup test users
│   └── verify_database.py       # Verify database state
└── README.md                     # This file
```

## Helper Scripts

### setup_test_user.py

Create or cleanup test users with specific plan configurations.

```bash
# Create user with plan (auto cleanup if exists)
docker exec devify-api-dev python /opt/devify/.cursor_tests/helpers/setup_test_user.py \
  --username test_billing_downgrade_user \
  --plan pro \
  --cleanup-first

# Only cleanup
docker exec devify-api-dev python /opt/devify/.cursor_tests/helpers/setup_test_user.py \
  --username test_billing_downgrade_user \
  --cleanup-only
```

### verify_database.py

Verify user's subscription and credits state.

```bash
docker exec devify-api-dev python /opt/devify/.cursor_tests/helpers/verify_database.py \
  --username test_billing_downgrade_user \
  --expect-plan pro \
  --expect-status active
```


## Manual Execution Example

Here's how to manually run Scenario 3 (Downgrade):

```bash
# 1. Prepare test user
docker exec devify-api-dev python /opt/devify/.cursor_tests/helpers/setup_test_user.py \
  --username test_billing_downgrade_user --plan pro --cleanup-first

# 2. Login at http://localhost:8000/login
#    Username: test_billing_downgrade_user
#    Password: Test123456!

# 3. Switch UI to English (click 🇺🇸 button)

# 4. Navigate to Plan & Billing page

# 5. Click "Downgrade to Standard Plan" button

# 6. Confirm in dialog

# 7. Verify database
docker exec devify-api-dev python /opt/devify/.cursor_tests/helpers/verify_database.py \
  --username test_billing_downgrade_user --expect-plan pro

# 8. Cleanup
docker exec devify-api-dev python /opt/devify/.cursor_tests/helpers/setup_test_user.py \
  --username test_billing_downgrade_user --cleanup-only
```

## Test Execution

### Using Cursor Built-in Browser

Cursor AI will execute tests using its built-in browser tools:
- Navigate to pages
- Fill forms
- Click buttons
- Verify UI changes
- Take screenshots when needed

All test results are displayed in the Cursor conversation.

## Benefits

1. **No External Dependencies**: Uses Cursor's built-in browser tools only
2. **Human Readable**: Markdown scenarios are easy to understand and modify
3. **Reproducible**: Fixed usernames and auto-cleanup ensure consistent environment
4. **Container-aware**: Properly handles Docker-based development environment
5. **Extensible**: Easy to add new test scenarios for any module
6. **Simple & Direct**: No complex test frameworks, just helper scripts + manual verification

## Multi-language Email Support

### Overview

Payment notification emails are automatically sent in the user's preferred language:
- **English** (en-US)
- **简体中文** (zh-CN)
- **Español** (es)

### How It Works

```python
# System automatically detects user language
user.profile.language  # e.g., 'zh-CN'
      ↓
Django i18n translation system
      ↓
Email sent in Chinese
```

### Supported Languages

| Profile Language | Email Language | Subject Example |
|-----------------|----------------|-----------------|
| `en-US` | English | "⚠️ Payment Failed - Action Required" |
| `zh-CN` | 简体中文 | "⚠️ 支付失败 - 需要立即处理" |
| `es` | Español | "⚠️ Pago Fallido - Acción Requerida" |

### Testing Multi-language

**Check user's language:**
```bash
docker exec devify-api-dev python manage.py shell -c "
from django.contrib.auth.models import User
user = User.objects.get(username='xiaoquqi')
print(f'Language: {user.profile.language}')
"
```

**Verify email language in logs:**
```bash
docker logs devify-worker-dev --tail 50 | grep "language:"
# Output: INFO Sent payment failure notification (language: zh-hans)
```

### Translation Files

Located in: `billing/locale/`
```
billing/locale/
├── zh_Hans/LC_MESSAGES/
│   ├── django.po  # Human-editable translations
│   └── django.mo  # Compiled binary
└── es/LC_MESSAGES/
    ├── django.po
    └── django.mo
```

**To update translations:**
```bash
# Extract new strings
docker exec devify-api-dev django-admin makemessages -l zh_Hans -l es

# Edit .po files manually

# Compile
docker exec devify-api-dev django-admin compilemessages

# Restart services
docker compose -f ../devify/docker-compose.dev.yml restart devify-worker
```

## Troubleshooting

### Scripts Can't Access Database

**Issue**: `ModuleNotFoundError` or connection errors

**Solution**: Ensure scripts run inside container:
```bash
docker exec devify-api-dev python /opt/devify/.cursor_tests/helpers/xxx.py
```

### Test User Already Exists

**Issue**: User creation fails

**Solution**: Use `--cleanup-first` flag:
```bash
--cleanup-first
```

### Container Not Running

**Issue**: `docker exec` fails

**Solution**: Start containers:
```bash
cd /home/ubuntu/workspace/devify_workspace/devify
docker compose -f docker-compose.dev.yml up -d
```

## Contributing

To add new test scenarios:

1. Create scenario file: `scenarios/{module}_{number}_{name}.md`
2. Use fixed test username: `test_{module}_{name}_user`
3. Follow the standard format (see existing scenarios)
4. Test manually before committing
5. Update this README with new scenario

## License

Internal use only. Not for distribution.
