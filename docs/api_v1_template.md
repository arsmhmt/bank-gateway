# LiderPay API v1 – Banka Havale & Kripto Ödeme

This document describes the **LiderPay API v1** for:

- **BANKA HAVALE (BANK)** – bank transfer deposits & withdrawals  
- **KRİPTO ÖDEME (CRYPTO)** – crypto deposits & withdrawals

> ⚠️ **Credit Card (CARD) is not part of this version** and should be ignored for now.

---

## 1. Base URL & Version

Use the base URL provided by your operator.

Examples:

- Production: `https://lider-pay.com`
- Staging: `https://staging.lider-pay.com`

All API endpoints are relative to this base, for example:

- `POST {base_url}/api/v1/deposit/create`
- `POST {base_url}/api/v1/withdraw/create`
- `GET  {base_url}/api/v1/transaction/status`

---

## 2. Authentication

Each betting site (operator) has its own **API key**.

You can find your API key in the **Site Panel → API Yönetimi** page.

You must send the API key in every request using **one** of these options:

### 2.1. HTTP Header (recommended)

```
X-API-KEY: YOUR_API_KEY_HERE
```

### 2.2. Query Parameter (alternative)

```
?api_key=YOUR_API_KEY_HERE
```

If both are present, the header may be preferred.
Requests without a valid api_key will be rejected with an authentication error.


## 3. Gateways & Currencies

### 3.1. Gateways

The gateway field controls which payment engine is used:

- BANK → Bank transfer (Banka Havale)
- CRYPTO → Crypto payments (Kripto Ödeme)

The enabled gateways per site are managed by the operator in the Yönetim Paneli.
If you try to use a gateway that is disabled for your site, the API will return a GATEWAY_DISABLED error.

### 3.2. Currencies

Supported currencies (example set, check with your operator):

- TRY
- USD
- EUR
- USDT

The currency field is required.
If omitted, the system may default to TRY (depending on config), but you should always send it explicitly.

## 4. Standard Response Format

All JSON responses follow a common envelope:

```json
{
  "success": true,
  "code": "OK",
  "message": "Optional human-readable message",
  "data": { }
}
```

- success – true or false
- code – short machine-readable code (see Error Codes section)
- message – optional human-readable description
- data – optional payload (object) containing result details

On errors:

```json
{
  "success": false,
  "code": "VALIDATION_REQUIRED_FIELDS",
  "message": "gateway, amount, external_user_id and currency are required.",
  "data": null
}
```

Note: The canonical machine-readable field is `code`. For backward compatibility some responses may also include `error_code` with the same value.

## 5. Endpoint: Create Deposit

### 5.1. URL

POST /api/v1/deposit/create

### 5.2. Description

Creates a deposit request for a player, via:

- Bank transfer (gateway = "BANK")
- Crypto (gateway = "CRYPTO")

### 5.3. Request Headers

- Content-Type: application/json
- X-API-KEY: YOUR_API_KEY_HERE

### 5.4. Request Body (JSON)

Common fields:

```json
{
  "gateway": "BANK",
  "external_user_id": "player123",
  "amount": 100.00,
  "currency": "TRY",
  "payment_token": "optional-client-side-id"
}
```

- gateway (string, required): "BANK" or "CRYPTO"
- external_user_id (string, required): your internal player ID or username
- amount (number, required): deposit amount
- currency (string, required): one of TRY, USD, EUR, USDT
- payment_token (string, optional but recommended):

  Your own idempotency key (max length depends on implementation).

  If omitted, LiderPay will generate one.

Additional fields may be added in future versions (e.g., metadata, language).

### 5.5. Successful Response (BANK example)

```json
{
  "success": true,
  "code": "OK",
  "message": null,
  "data": {
    "transaction_id": "123456",
    "payment_token": "abc123xyz",
    "gateway": "BANK",
    "status": "pending",
    "currency": "TRY",
    "amount": 100.0
  }
}
```

### 5.6. Successful Response (CRYPTO example)

```json
{
  "success": true,
  "code": "OK",
  "message": null,
  "data": {
    "transaction_id": "789010",
    "payment_token": "crypto-xyz-001",
    "gateway": "CRYPTO",
    "status": "pending",
    "currency": "USDT",
    "amount": 50.0,
    "coin": "USDT",
    "network": "TRC20"
  }
}
```

### 5.7. Idempotency

payment_token is treated as an idempotency key.

If the same payment_token is sent again with the same parameters:

- The API should return the existing transaction instead of creating a new one.
- If there is a conflict (same payment_token with different data), an error code such as VALIDATION_IDEMPOTENCY_CONFLICT may be returned.

## 6. Endpoint: Create Withdrawal

### 6.1. URL

POST /api/v1/withdraw/create

### 6.2. Description

Creates a withdrawal request for a player via:

- Bank transfer (gateway = "BANK")
- Crypto (gateway = "CRYPTO")

### 6.3. Request Headers

- Content-Type: application/json
- X-API-KEY: YOUR_API_KEY_HERE

### 6.4. Request Body (JSON)

Common fields:

```json
{
  "gateway": "BANK",
  "external_user_id": "player123",
  "amount": 200.00,
  "currency": "TRY",
  "payment_token": "withdraw-001"
}
```

Depending on the gateway, additional info may be required:

- For BANK: IBAN / account info is usually stored or handled through your own system or via a separate flow.
- For CRYPTO: Payout address may be taken from your system and not supplied via API; or a separate integration might be agreed with the operator.

Check with your operator if extra fields are needed in your environment.

### 6.5. Successful Response

```json
{
  "success": true,
  "code": "OK",
  "message": null,
  "data": {
    "transaction_id": "654321",
    "payment_token": "withdraw-001",
    "gateway": "BANK",
    "status": "pending",
    "currency": "TRY",
    "amount": 200.0
  }
}
```

Idempotency semantics are similar to the deposit endpoint.

## 7. Endpoint: Transaction Status

### 7.1. URL

GET /api/v1/transaction/status

### 7.2. Description

Returns the status of a transaction created via deposit or withdraw API.

### 7.3. Query Parameters

- payment_token=YOUR_PAYMENT_TOKEN

Optionally you may also provide transaction_id, depending on final implementation, but payment_token is the primary key for external systems.

### 7.4. Example Request

```bash
curl "{{base_url}}/api/v1/transaction/status?payment_token=abc123xyz" \
  -H "X-API-KEY: YOUR_API_KEY_HERE"
```

### 7.5. Successful Response

```json
{
  "success": true,
  "code": "OK",
  "message": null,
  "data": {
    "transaction_id": "123456",
    "payment_token": "abc123xyz",
    "gateway": "BANK",
    "type": "DEPOSIT",
    "status": "approved",
    "currency": "TRY",
    "amount": 100.0,
    "tx_hash": null,
    "created_at": "2025-01-01T12:00:00Z",
    "approved_at": "2025-01-01T12:05:00Z"
  }
}
```

For crypto transactions, tx_hash, coin, and network may be present:

```json
"tx_hash": "abcd1234...",
"coin": "USDT",
"network": "TRC20"
```

### 7.6. Not Found

```json
{
  "success": false,
  "code": "NOT_FOUND",
  "message": "Transaction not found for this payment_token.",
  "data": null
}
```

## 8. Error Codes (Examples)

Below is a non-exhaustive list of error codes. The exact set depends on the implementation.

### 8.1. Authentication / Authorization

- AUTH_INVALID_API_KEY
  - Invalid or missing api_key / X-API-KEY.

- AUTH_SITE_DISABLED
  - The site/operator is not allowed to use the API.

### 8.2. Validation

- VALIDATION_REQUIRED_FIELDS
  - One or more required fields are missing (gateway, amount, external_user_id, currency).

- VALIDATION_CURRENCY_INVALID
  - Currency not in the allowed list (TRY, USD, EUR, USDT, etc.).

- VALIDATION_AMOUNT_INVALID
  - Amount is zero, negative, or above configured limits.

- VALIDATION_GATEWAY_INVALID
  - gateway is not one of "BANK" or "CRYPTO".

- VALIDATION_IDEMPOTENCY_CONFLICT
  - payment_token was reused with conflicting data.

### 8.3. Gateway State

- GATEWAY_DISABLED
  - The requested gateway (BANK/CRYPTO) is disabled for this site.

- GATEWAY_TEMPORARILY_UNAVAILABLE
  - The gateway is temporarily unavailable (maintenance).

### 8.4. Internal / Server Errors

- INTERNAL_ERROR
  - Unexpected server-side error (check logs or contact support).

## 9. Operational Notes

### Bank Deposits (BANK)

After the deposit is created, the player is expected to complete the bank transfer.

Final approval is done by provider/admin workflows inside LiderPay.

### Crypto Deposits (CRYPTO)

Deposits are created as pending.

Confirmation is performed:

- Automatically via on-chain listener (for supported networks, e.g. USDT/TRC20), or
- Manually by operators in the admin panel.

You should periodically poll the transaction/status endpoint or rely on callbacks (if configured with your operator).

### Idempotency

Always send a stable payment_token per deposit/withdraw request to safely retry without creating duplicates.

## 10. Support

For integration questions:

Check the Site Panel → API Yönetimi page for your specific site.

Contact your operator or technical support with:

- Example request/response
- Timestamp
- payment_token and/or transaction_id
- Environment (staging/production)

---

If you like this structure, just:

- Create `docs/api_v1_template.md` in your repo,
- Paste the above,
- Adjust base URLs, currencies, and any codes that differ from your actual implementation.

Next best step on your side:

1. **Run migrations + tests** (so DB matches code).
2. Add **2–3 minimal API tests** (BANK deposit, CRYPTO deposit, status).
3. Then you can safely tell the client:  
   “Hosted pages are live, and API v1 is ready for initial integration with this spec.”
