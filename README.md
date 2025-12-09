LiderPay — bank-gateway

Overview

This repository contains the LiderPay gateway project (Django). Key features:

- Bank transfer (BANK) and Crypto (CRYPTO) payment flows
- API v1 endpoints under `/api/v1/...` for integrations
- Site panel for operators to manage API keys and settings

Important operational notes

- Migrations: run `python manage.py migrate` on staging/production before starting services.
- Static files: `python manage.py collectstatic --noinput` for production.

Crypto poller

See `docs/crypto_poller.md` for sample `systemd` and `cron` entries to run the `poll_crypto_deposits` management command. This poller confirms on-chain crypto deposits and should run periodically (recommended every 5 minutes).

API docs

See `docs/api_v1_template.md` for the API contract and examples.
