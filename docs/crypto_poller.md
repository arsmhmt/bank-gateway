# Crypto Poller (poll_crypto_deposits)

This document shows simple ways to run the Django management command that scans on-chain activity and confirms crypto deposits.

Management command

- Command name (example):

  ```bash
  python manage.py poll_crypto_deposits
  ```

  Adjust the command according to your Python/virtualenv paths and `DJANGO_SETTINGS_MODULE` if needed.

Systemd (recommended on Linux)

1) Service unit: `/etc/systemd/system/liderpay-crypto-poller.service`

```
[Unit]
Description=LiderPay Crypto Poller
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
Environment=DJANGO_SETTINGS_MODULE=config.settings
ExecStart=/path/to/venv/bin/python /path/to/project/manage.py poll_crypto_deposits
Restart=on-failure
RestartSec=10s
StandardOutput=append:/var/log/liderpay/crypto_poller.log
StandardError=inherit

[Install]
WantedBy=multi-user.target
```

2) Timer unit (run every 5 minutes): `/etc/systemd/system/liderpay-crypto-poller.timer`

```
[Unit]
Description=Run LiderPay Crypto Poller every 5 minutes

[Timer]
OnCalendar=*:0/5
Persistent=true
Unit=liderpay-crypto-poller.service

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now liderpay-crypto-poller.timer
sudo systemctl status liderpay-crypto-poller.timer
```

This will trigger the `liderpay-crypto-poller.service` every 5 minutes.

Cron (simple alternative)

Add a cron entry for the desired user (e.g. `www-data` or the deployment user):

```cron
*/5 * * * * /path/to/venv/bin/python /path/to/project/manage.py poll_crypto_deposits >> /var/log/liderpay/crypto_poller.log 2>&1
```

Notes & recommendations

- Logging: point logs to a managed location (e.g. `/var/log/liderpay/crypto_poller.log`) and rotate logs with `logrotate`.
- Permissions: ensure the service user has access to the project directory, venv, and DB/keys.
- Environment: If your deployment relies on environment variables (e.g., `DJANGO_SETTINGS_MODULE`, external node RPC creds), ensure they are exported in the service unit or available in the environment where cron runs.
- Monitoring: configure Sentry (or similar) for unhandled exceptions and a simple healthcheck alert when the poller fails repeatedly.
- Testing: run the command manually after deployment to confirm it completes without errors.

Troubleshooting

- Use `journalctl -u liderpay-crypto-poller.service` to inspect logs when using systemd.
- Check `/var/log/liderpay/crypto_poller.log` for cron output.
- If the command fails with database errors, confirm migrations were applied and the DB user permissions are correct.

If you want, I can also:
- Generate a sample `logrotate` snippet for `/var/log/liderpay/crypto_poller.log`.
- Add a small `deploy/poller` script to the repo to simplify starting the service on new hosts.
