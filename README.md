# 🏎️ ACC Server Monitor

**Automated monitoring solution for Assetto Corsa Competizione servers with Discord notifications**

![https://python.org](https://img.shields.io/badge/python-3.12+-blue.svg) ![License](https://img.shields.io/badge/license-MIT-green.svg) ![https://github.com/features/actions](https://img.shields.io/badge/platform-GitHub%20Actions-orange.svg) ![https://discord.com](https://img.shields.io/badge/notifications-Discord-7289da.svg) ![https://acc-status.jonatan.net](https://img.shields.io/badge/data%20source-acc--status.jonatan.net-blueviolet.svg)

---

## Overview

ACC Server Monitor is a **free**, **automated monitoring solution** that tracks the health and performance of Assetto Corsa Competizione servers using the acc-status.jonatan.net API.

Get **real-time Discord notifications** when server status changes, with detailed metrics including *ping*, *server count*, and *player activity*.

## Key Features

- **Automated Monitoring** - Runs every 15 minutes to check server status via GitHub Actions.
- **Smart Discord Notifications** - Rich embeds with server status and metrics.
- **Real-time Metrics** - Ping, server count, player activity, and uptime tracking.
- **Intelligent Status Detection** - `UP`, `DEGRADED` and `DOWN` with detailed reasons.
- **Historical Data** - Tracks last 200 monitoring entries (~17 hours of data).
- **Timezone-Aware** - Proper UTC handling for date calculations.
- **Zero Infrastructure** - No servers, databases, or paid services required.

## Quick Start

### Prequisites

- Github account with repository access
- Discord server with webhook permission
- 2 minutes to set up

### 1. Setup repository

```bash
# Option A: Use this template
Click "Use this template" → Create new repository

# Option B: Fork this repository
Click "Fork" → Create fork

# Option C: Clone manually from a terminal
git clone https://github.com/CR0ZER/acc-server-check.git
cd acc-server-check
```

### 2. Configure Discord Webhook

1. Discord server settings → Integrations → Webhooks
2. Create a new webhook
3. Copy the webhook URL

### 3. Add GitHub Secrets

1. Your repository → Settings → Secrets and variables → Actions
2. New repository secret
3. Name: `DISCORD_WEBHOOK_URL`
4. Secret: Paste your Discord webhook URL (e.g. `https://discord.com/api/webhooks/YOUR/WEBHOOK/URL`)
5. Add secret

### 4. Activate Monitoring

```bash
# Push any change to trigger the workflow
git commit --allow-empty -m "Trigger monitoring"
git push

# Or manually trigger
Actions → ACC Monitor → Run workflow
```

That's it! The monitoring is now active and will run automatically every 15 minutes.

## Discord Notifications

> Notifications are only sent when there is a significant change in server status or if the API is unreachable. This helps reduce noise and ensures you only get notified when it matters. You can still manually trigger notifications in github actions with the `force notification` option.

Notifications are sent to your Discord server with rich embeds containing:

**Server Online**

```
🟢 ACC SERVERS ONLINE
📊 State Detected: UP
🤖 API Status: 1 (UP)
🏓 Ping Servers: 45ms
🖥️ Servers Online: 1,823
👥 Players Online: 1,205
🟢 Data Age: 2.3 minutes ago
⏱️ API Response Time: 0.34s
```

**Server Degraded**

```
🟠 ACC SERVERS DEGRADED
📊 State Detected: DEGRADED
🟡 Ping Servers: 180ms
🟡 Servers Online: 892
⚠️ Issues Detected:
- ACC ping warning: 180ms (> 100ms)
- ACC servers count decreasing (892)
```

**Server Down**

```
🔴 ACC SERVERS OFFLINE
📊 State Detected: DOWN
🤖 API Status: 0 (DOWN)
⏳ Duration Offline: 2h 15min
```

## Configuration

### Monitoring Frequency

Edit `.github/workflows/acc-monitor.yml`:

> The default is every 15 minutes, the API updates every 5 minutes. You can change this to any value you want, but it is recommended to keep a multiple of 5 minutes to avoid API caching issues.

```yaml
schedule:
  - cron: '*/5 * * * *'   # Every 5 minutes (optimal)
  - cron: '*/15 * * * *'  # Every 10 minutes (default)
  - cron: '0 * * * *'     # Every hour
```

### Alert Thresholds

Edit `acc_monitor.py`:

```python
self.config = {
    'max_acceptable_ping': 150,     # ms - Maximum acceptable ping
    'min_servers_expected': 1000,   # Minimum expected server count
    'max_data_age_minutes': 15,     # Maximum age for data freshness
    'warning_ping': 100,            # ms - Warning threshold for ping
    'warning_servers': 1200,        # Warning threshold for servers
}
```

### Notification Settings

Edit `acc_monitor.py`:

```python
significant_change = (
    last_status != current_status or            # If status changed
    current_status in ['DOWN', 'API_ERROR'] or  # Critical status
    force_notification                          # Manual trigger with GitHub Actions input
)
```

## Testing & Development

### Local Testing

You can test the script locally by running `acc_monitor.py` or `test_local.py` with **Python 3.12+**. Running `test_local.py` will execute the monitoring logic and testing all features with enhanced logging.

```python
# Install dependencies
pip install -r requirements.txt

# Run local monitoring to test all features and check if any issues arise
python test_local.py

# Set Discord webhook for testing the full monitoring flow
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR/WEBHOOK"

# Run one-shot monitoring locally
python acc_monitor.py

# Test with force notification
export FORCE_NOTIFICATION=true
python acc_monitor.py
```

### Manual Actions Trigger

```bash
# GitHub interface:
Actions → ACC Monitor → Run workflow
☑️ Force notification: true
→ Run workflow
```

### File Structure

```
├── acc_monitor.py            # Main monitoring script
├── test_local.py             # Local testing script
├── requirements.txt          # Python dependencies
└── .github/workflows/
    └── acc-monitor.yml       # GitHub Actions workflow
```

### Status Logic

#### Status Definitions

| Conditions | Status | Notification |
|------------|-----|----------------|
| API Status = 1, All metrics good | `UP` | On change only |
| API Status = 1, Minor issues | `DEGRADED` | On change only |
| API Status = 0 | `DOWN` | Immediate + repeated |
| API Status = -1 | `UNKNOWN` | On change only |
| API unreachable | `API_ERROR` | Immediate |

#### Issue Detection

- Ping > `max_acceptable_ping` (configurable)
- Server count < `min_servers_expected` (configurable)
- Data age > `max_data_age_minutes` (configurable)
- API unreachable or error

### Usage of GitHub Actions

A run for the project has a duration of about 20 seconds.
The **Free Tier** of GitHub Actions provides **2,000 minutes per month** for public repositories.

> **Warning:** If you decide to trigger the monitoring every 5 minutes to follow the API, you will use about 2,851 minutes per month, which is more than the free tier.

## Contributing

Contributions are welcome! Please feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

This project uses the [acc-status.jonatan.net](https://acc-status.jonatan.net/) API as the data source for Assetto Corsa Competizione server status.

## Support

- Bug reports: [Open an Issue](https://github.com/CR0ZER/acc-server-check/issues)
- Feature requests: [Open an Issue](https://github.com/CR0ZER/acc-server-check/issues)

---

**⭐ If this project helps you monitor your ACC servers, please give it a star!

🏎️ Happy Racing!**
