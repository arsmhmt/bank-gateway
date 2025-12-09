LiderPay Unified Payment Platform (BANK + CARD + CRYPTO)
Architecture by: ChatGPT (Architect)
Implementation by: Codex (Coder)
Strategic direction: User (Brain)
✅ PHASE 1 — FOUNDATION: MULTI-GATEWAY ARCHITECTURE
1.1 Create GatewayType enum

File: core/models.py

Add:

class GatewayType(models.TextChoices):
    BANK = "BANK", "Bank Transfer"
    CARD = "CARD", "Credit Card"
    CRYPTO = "CRYPTO", "Crypto"

1.2 Create PaymentTransaction model

File: core/models.py

Codex must implement universal record for ALL gateways:

class PaymentTransaction(models.Model):
    branch = models.ForeignKey("branches.Branch", on_delete=models.CASCADE)
    gateway = models.CharField(max_length=10, choices=GatewayType.choices)
    direction = models.CharField(max_length=10, choices=[("IN", "Deposit"), ("OUT", "Withdraw")])
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="TRY")
    user_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, default="pending")
    ref_code = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional gateway detail references
    bank_deposit = models.ForeignKey("bank.BankDeposit", null=True, blank=True, on_delete=models.SET_NULL)
    card_payment = models.ForeignKey("card.CardPayment", null=True, blank=True, on_delete=models.SET_NULL)
    crypto_payment = models.ForeignKey("crypto.CryptoPayment", null=True, blank=True, on_delete=models.SET_NULL)


Acceptance Criteria:

Migrations must run without errors.

Bank deposits continue functioning.

1.3 Create SiteGatewayConfig model

File: branches/models.py

Codex must create:

class SiteGatewayConfig(models.Model):
    branch = models.ForeignKey("branches.Branch", related_name="gateway_configs", on_delete=models.CASCADE)
    gateway = models.CharField(max_length=10, choices=GatewayType.choices)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        unique_together = ("branch", "gateway")


Purpose:
Enable/disable BANK / CARD / CRYPTO per branch.

✅ PHASE 2 — PUBLIC PAYMENT ROUTES FOR ALL GATEWAYS
2.1 Create folder: public_gateway/

Files:

public_gateway/views_bank.py

public_gateway/views_card.py

public_gateway/views_crypto.py

public_gateway/utils.py

2.2 Public URL patterns

File: urls.py

Codex must register:

path("p/<slug:code>/bank/deposit/", views_bank.deposit_form),
path("p/<slug:code>/bank/withdraw/", views_bank.withdraw_form),

path("p/<slug:code>/card/deposit/", views_card.deposit_form),
path("p/<slug:code>/card/withdraw/", views_card.withdraw_form),

path("p/<slug:code>/crypto/deposit/", views_crypto.deposit_form),
path("p/<slug:code>/crypto/withdraw/", views_crypto.withdraw_form),

2.3 Permission enforcement

Inside each view:

branch = get_branch_from_public_code()
if not branch.gateway_configs.filter(gateway="BANK", is_enabled=True).exists():
    return HttpResponseForbidden("Gateway disabled for this site.")


Must be applied for BANK / CARD / CRYPTO pages.

✅ PHASE 3 — UI: MULTI-GATEWAY PAYMENT FORM
3.1 Create tabbed deposit page

Base template: templates/public/deposit_base.html

Tabs:

[ BANK ] [ CREDIT CARD ] [ CRYPTO ]


Only show tabs for gateways where .is_enabled=True.

Each tab loads a partial:

_bank_form.html

_card_form.html

_crypto_form.html

✅ PHASE 4 — BANK GATEWAY ADAPTATION

Bank gateway = already exists.
Codex must:

Modify existing bank deposit creation to also create a PaymentTransaction row linked to the BankDeposit.

No functional changes.

Provider (Teminci) remains exclusive to BANK gateway.

✅ PHASE 5 — CARD GATEWAY IMPLEMENTATION (SKELETON)
5.1 Create card app

Files:

card/models.py

card/views.py

card/services.py

5.2 Implement skeleton model
class CardPayment(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    user_name = models.CharField(max_length=150)
    psp_tx_id = models.CharField(max_length=120, null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")

5.3 Public deposit view

Create transaction

Redirect to “Card Payment Pending” page

Skeleton only, PSP integration later.

Acceptance Criteria:

Form submits

CardPayment created

PaymentTransaction created

✅ PHASE 6 — CRYPTO GATEWAY IMPLEMENTATION (SKELETON)
6.1 Create crypto app

Files:

crypto/models.py

crypto/views.py

crypto/services.py

6.2 Implement basic model
class CryptoPayment(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    coin = models.CharField(max_length=20)
    network = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    address = models.CharField(max_length=120)
    tx_hash = models.CharField(max_length=120, blank=True, null=True)
    status = models.CharField(max_length=20, default="pending")

6.3 Public deposit view

Generate address placeholder

Store CryptoPayment

Create PaymentTransaction

Show address + QR

Acceptance Criteria:

Form submits

CryptoPayment created

PaymentTransaction created

✅ PHASE 7 — ADMIN PANEL UPDATES
7.1 System Admin Panel

Sidebar:

Gateways
   - Bank Gateway
   - Credit Card Gateway
   - Crypto Gateway
Sites
   - Manage Gateways (per site)
   - Gateway URLs (per site)


Admin must be able to:

Toggle gateway active/inactive per site

View public URLs for all gateways:

/p/<code>/bank/*

/p/<code>/card/*

/p/<code>/crypto/*

7.2 Site Panel

Site sees ONLY gateways with is_enabled=True.

Sidebar example:

Payments
   - Bank Payments   (if bank enabled)
   - Credit Card     (if card enabled)
   - Crypto          (if crypto enabled)
Integration
   - Gateway URLs    (only enabled URLs)

✅ PHASE 8 — QUERY PARAM SUPPORT

All gateway deposit pages must support:

?user=USERNAME&amount=123


Pre-fill the form if values exist.

✅ PHASE 9 — FUTURE-PROOFING

Add TODO placeholders for:

PSP 3D integration

Blockchain confirmation listener

Deposit/withdraw callbacks

BetConstruct API mapping

Multi-currency support

🎯 FINAL ACCEPTANCE CRITERIA

Codex must deliver:

Working multi-gateway system

Branch-level gateway activation

Public URLs fully separated per gateway

Unified PaymentTransaction table

Bank → functional

Card → skeleton working

Crypto → skeleton working

Site panel gateway visibility correct

Admin panel gateway toggling correct

CODEX COMMANDS — LiderPay Multi-Gateway Implementation Plan

(Matches TODO.md phases exactly.)

=========================================
PHASE 1 — MULTI-GATEWAY CORE ARCHITECTURE
=========================================
✅ Command 1: Create GatewayType enum
CODEX:
Create or update core/models.py and implement:

class GatewayType(models.TextChoices):
    BANK = "BANK", "Bank Transfer"
    CARD = "CARD", "Credit Card"
    CRYPTO = "CRYPTO", "Crypto"

Run makemigrations + migrate.

✅ Command 2: Implement PaymentTransaction model
CODEX:
In core/models.py, add PaymentTransaction model with fields:

branch (FK Branch)
gateway (choices=GatewayType)
direction (IN/OUT)
amount
currency="TRY"
user_name
status (pending/approved/rejected/failed)
ref_code (unique)
timestamps
Optional FK fields:
  bank_deposit
  card_payment
  crypto_payment

Create migrations and migrate.

✅ Command 3: Implement SiteGatewayConfig model
CODEX:
In branches/models.py:

Create model SiteGatewayConfig with:
- branch FK
- gateway (choices=GatewayType)
- is_enabled bool
Add unique_together(branch, gateway)

Run migrations.

=========================================
PHASE 2 — PUBLIC ROUTING FOR BANK / CARD / CRYPTO
=========================================
✅ Command 4: Create public_gateway module
CODEX:
Create new folder public_gateway/
Add:
- views_bank.py
- views_card.py
- views_crypto.py
- utils.py (helper for resolving branch by public_code)

✅ Command 5: Register public URLs
CODEX:
Edit project urls.py and add routes:

/p/<slug:code>/bank/deposit/
/p/<slug:code>/bank/withdraw/
/p/<slug:code>/card/deposit/
/p/<slug:code>/card/withdraw/
/p/<slug:code>/crypto/deposit/
/p/<slug:code>/crypto/withdraw/

Map them to respective view modules.

✅ Command 6: Enforce site gateway permissions
CODEX:
In every public gateway view (bank/card/crypto):
After resolving branch from public_code,
check SiteGatewayConfig for matching gateway and is_enabled=True.
If not enabled, return 403 or 404.

=========================================
PHASE 3 — MULTI-GATEWAY FRONTEND
=========================================
✅ Command 7: Create deposit tab UI
CODEX:
In templates/public/, create deposit_base.html:

- Tabs: Bank, Card, Crypto
- Only show enabled gateways for branch
- Load _bank_form.html, _card_form.html, _crypto_form.html partials

Add minimal styling; logic first.

✅ Command 8: Add query param prefill
CODEX:
In each public deposit view:
If request.GET contains ?user= & ?amount=
prefill the form context with these values.

=========================================
PHASE 4 — BANK GATEWAY ADAPTATION
=========================================
✅ Command 9: Update bank deposit creation to also create PaymentTransaction
CODEX:
Whenever a BankDeposit is created:
Immediately create PaymentTransaction with:
  gateway=BANK
  direction=IN
  branch = same branch
  user_name
  amount
  status="pending"
  bank_deposit reference

Do NOT modify existing provider logic.

=========================================
PHASE 5 — CARD GATEWAY SKELETON
=========================================
✅ Command 10: Create card app
CODEX:
Create new Django app "card".
Add models.py, views.py, services.py.
Register app in settings.

✅ Command 11: Implement CardPayment model
CODEX:
In card/models.py implement:

class CardPayment(models.Model):
    branch FK
    amount
    user_name
    psp_tx_id null
    status = pending

Run migrations.

✅ Command 12: Implement card deposit flow (skeleton)
CODEX:
In public_gateway/views_card.py:
- Validate SiteGatewayConfig
- Create CardPayment
- Create PaymentTransaction linked to card_payment
- Show "Card Payment Pending" template

=========================================
PHASE 6 — CRYPTO GATEWAY SKELETON
=========================================
✅ Command 13: Create crypto app
CODEX:
Create new Django app "crypto".
Add models.py, views.py, services.py.
Register app in settings.

✅ Command 14: Implement CryptoPayment model
CODEX:
In crypto/models.py implement:

class CryptoPayment(models.Model):
    branch FK
    coin
    network
    amount
    address
    tx_hash null
    status=pending

Run migrations.

✅ Command 15: Implement crypto deposit flow (skeleton)
CODEX:
In public_gateway/views_crypto.py:
- Validate SiteGatewayConfig
- Generate dummy crypto deposit address (placeholder)
- Create CryptoPayment
- Create PaymentTransaction linked to crypto_payment
- Show deposit address + QR template

=========================================
PHASE 7 — ADMIN PANEL ENHANCEMENTS
=========================================
✅ Command 16: Add gateway management UI for System Admin
CODEX:
In admin_panel:
Add sidebar section "Gateways" with:
- Bank Gateway
- Credit Card Gateway
- Crypto Gateway

Add page per site:
- Toggle gateway ON/OFF (SiteGatewayConfig)
- Show public URLs per gateway

✅ Command 17: Update Site Panel to show only enabled gateways
CODEX:
In site_panel:
Modify sidebar menu:
- Show Bank only if BANK enabled
- Show Card only if CARD enabled
- Show Crypto only if CRYPTO enabled

Add Integration page showing only enabled gateway URLs.

=========================================
PHASE 8 — FINAL TOUCHES
=========================================
✅ Command 18: Apply gateway filtering to API integration
CODEX:
In /api/deposit/create and /api/withdraw/create:
Expect parameter "gateway".
Check SiteGatewayConfig before processing.
If gateway disabled → return error.

✅ Command 19: Add error handling templates
CODEX:
Add templates:
- public/errors/gateway_disabled.html
- public/errors/invalid_request.html

✅ Command 20: Testing & validation
CODEX:
Test scenarios:

1. Site with only BANK enabled → only bank URLs work.
2. Site with only CARD enabled → card form loads, bank disabled.
3. Site with all 3 enabled → all three tabs appear.
4. Public pages reject unauthorized gateways.
5. PaymentTransaction created for bank/card/crypto.

1️⃣ Migration order (to avoid circular hell)

Assuming current project already has:

core (User, maybe existing bank models)

branches

bank / banking (DepositRequest/BankAccount/Provider)

admin_panel, site_panel, provider_panel

New things we add: PaymentTransaction, SiteGatewayConfig, card, crypto, public_gateway.

Recommended order:

Add GatewayType + PaymentTransaction (without FKs to new apps yet)

File: core/models.py

For now: comment out / omit card_payment and crypto_payment FKs (because card and crypto apps don’t exist yet).

makemigrations core → migrate

Add SiteGatewayConfig to branches

File: branches/models.py

makemigrations branches → migrate

Create card app + CardPayment model

python manage.py startapp card

Implement CardPayment with FK to Branch.

makemigrations card → migrate

Create crypto app + CryptoPayment model

python manage.py startapp crypto

Implement CryptoPayment with FK to Branch.

makemigrations crypto → migrate

Add FKs in PaymentTransaction pointing to CardPayment and CryptoPayment

Now that apps exist, update PaymentTransaction:

card_payment = models.ForeignKey("card.CardPayment", null=True, blank=True, on_delete=models.SET_NULL)
crypto_payment = models.ForeignKey("crypto.CryptoPayment", null=True, blank=True, on_delete=models.SET_NULL)


makemigrations core → migrate

Hook existing Bank deposits to PaymentTransaction

Update bank deposit creation code to also create a PaymentTransaction.

No schema changes; just code.

Add public_gateway module + URLs + templates

Pure code/templates: no migrations.

That order keeps dependencies clean and avoids cross-app import issues during migrations.

2️⃣ Folder structure tree (target layout)

Here’s a logical target tree for the repo (only important parts):

bank-gateway/
├── manage.py
├── settings.py
├── urls.py
├── wsgi.py
│
├── core/
│   ├── __init__.py
│   ├── models.py        # GatewayType, PaymentTransaction, maybe other core models
│   ├── utils/
│   ├── decorators.py
│   └── ...
│
├── branches/
│   ├── __init__.py
│   ├── models.py        # Branch, SiteGatewayConfig, etc.
│   ├── views.py
│   ├── admin.py
│   └── ...
│
├── bank/                # or banking/
│   ├── __init__.py
│   ├── models.py        # BankAccount, Provider, BankDeposit/DepositRequest, WithdrawalRequest
│   ├── views.py
│   ├── services.py
│   └── ...
│
├── card/
│   ├── __init__.py
│   ├── models.py        # CardPayment
│   ├── views.py         # card engine specific (backoffice, callbacks)
│   ├── services.py      # PSP integration logic
│   └── ...
│
├── crypto/
│   ├── __init__.py
│   ├── models.py        # CryptoPayment
│   ├── views.py         # internal crypto admin/callback endpoints
│   ├── services.py      # address generation, blockchain checks
│   └── ...
│
├── public_gateway/
│   ├── __init__.py
│   ├── utils.py         # get_branch_from_public_code, gateway checks
│   ├── views_bank.py    # public bank deposit/withdraw forms
│   ├── views_card.py    # public card deposit/withdraw forms
│   ├── views_crypto.py  # public crypto deposit/withdraw forms
│   └── ...
│
├── admin_panel/
│   ├── __init__.py
│   ├── urls.py
│   ├── views.py         # system admin dashboard + gateway config UI
│   └── ...
│
├── site_panel/
│   ├── __init__.py
│   ├── urls.py
│   ├── views.py         # site-level views, gateway URLs page, report views
│   └── ...
│
├── provider_panel/
│   ├── __init__.py
│   ├── urls.py
│   ├── views.py         # Teminci-only views, bank only
│   └── ...
│
└── templates/
    ├── base.html
    ├── admin_panel/
    ├── site_panel/
    ├── provider_panel/
    └── public/
        ├── deposit_base.html
        ├── bank_deposit_form.html
        ├── card_deposit_form.html
        ├── crypto_deposit_form.html
        ├── bank_withdraw_form.html
        ├── card_withdraw_form.html
        ├── crypto_withdraw_form.html
        └── errors/
            ├── gateway_disabled.html
            └── invalid_request.html


Codex doesn’t have to match this exact tree, but this is the direction.

3️⃣ Naming conventions (so everything stays consistent)
3.1. Gateways & enums

Enum class: GatewayType

Values: "BANK", "CARD", "CRYPTO"

Direction:

"IN" = deposit (money coming into LiderPay from user)

"OUT" = withdraw (money going out from LiderPay to user)

Status constants (shared):

"pending", "approved", "rejected", "failed", "expired"

Recommendation: define status choices in a reusable place (e.g. core/constants.py) and reuse across PaymentTransaction, BankDeposit, CardPayment, CryptoPayment.

3.2. Models

PaymentTransaction (unified view of all money movements)

BankDeposit, BankWithdrawal or DepositRequest, WithdrawalRequest (whatever you already use)

CardPayment

CryptoPayment

SiteGatewayConfig

Provider (Teminci), BankAccount, Branch

3.3. URLs (names)

Public:

public_bank_deposit

public_bank_withdraw

public_card_deposit

public_card_withdraw

public_crypto_deposit

public_crypto_withdraw

Site panel:

site_panel:gateway_urls

site_panel:transactions

site_panel:gateway_settings (if needed)

Admin panel:

admin_panel:site_gateway_list

admin_panel:site_gateway_edit

admin_panel:transactions

3.4. Templates

public/deposit_base.html

public/bank_deposit_form.html

public/card_deposit_form.html

public/crypto_deposit_form.html

public/errors/gateway_disabled.html

Use lowercase + underscores, grouped by feature.

4️⃣ Error code spec (for API + internal logic)

You already half-drafted some earlier; let’s clean it up into a stable list.

4.1. General structure

Every API response (error or success) should have:

{
  "success": false,
  "error_code": "GATEWAY_DISABLED",
  "message": "This gateway is not enabled for this merchant."
}


or:

{
  "success": true,
  "data": { ... }
}

4.2. Error codes

Authentication / security

AUTH_MISSING_HEADERS – Missing auth headers (API key, timestamp, signature).

AUTH_INVALID_SIGNATURE – Signature mismatch.

AUTH_INVALID_API_KEY – API key not recognized / inactive.

AUTH_MERCHANT_DISABLED – Merchant (branch) disabled.

Gateway / site configuration

GATEWAY_UNKNOWN – gateway value not one of BANK/CARD/CRYPTO.

GATEWAY_DISABLED – gateway not enabled for this site (SiteGatewayConfig.is_enabled=False).

GATEWAY_TEMPORARILY_UNAVAILABLE – gateway currently down/maintenance (global flag).

Validation

VALIDATION_INVALID_AMOUNT – amount <= 0 or outside allowed min/max.

VALIDATION_INVALID_CURRENCY – unsupported currency.

VALIDATION_INVALID_USER – user_name missing or invalid.

VALIDATION_INVALID_BANK – invalid bank_id or bank not active.

VALIDATION_INVALID_IBAN – IBAN failed regex/mask.

Resource not found

DEPOSIT_NOT_FOUND

WITHDRAW_NOT_FOUND

TRANSACTION_NOT_FOUND

State / business logic

LIMITOR_REACHED – Bank or provider limitor exceeded.

BANK_INACTIVE – bank account not active (maybe due to limit).

GATEWAY_NOT_READY – card/crypto gateway has no configured provider credentials.

System

INTERNAL_ERROR – unexpected error, log ID should be included.

Example INTERNAL_ERROR response:

{
  "success": false,
  "error_code": "INTERNAL_ERROR",
  "message": "An unexpected error occurred.",
  "log_id": "ERR-2025-03-01-XYZ123"
}


Log ID can be the primary key of an error-log row, or a UUID in logs.

5️⃣ Unified transaction admin table

You want one clear place where owner/admin can see everything passing through the system, regardless of gateway.

We’ll use the PaymentTransaction model for this.

5.1. Django admin registration (simple)

In core/admin.py:

from django.contrib import admin
from .models import PaymentTransaction

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "branch", "gateway", "direction",
                    "amount", "currency", "user_name", "status")
    list_filter = ("gateway", "direction", "status", "currency", "branch")
    search_fields = ("user_name", "ref_code")
    date_hierarchy = "created_at"


This gives you a quick generic view.

5.2. Custom admin-panel table (the one your owner will actually use)

In admin_panel/views.py, create a view like:

from django.shortcuts import render
from core.models import PaymentTransaction
from branches.models import Branch

def transactions_list(request):
    qs = PaymentTransaction.objects.select_related("branch").order_by("-created_at")

    gateway = request.GET.get("gateway")
    branch_id = request.GET.get("branch")
    status = request.GET.get("status")

    if gateway:
        qs = qs.filter(gateway=gateway)
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    if status:
        qs = qs.filter(status=status)

    branches = Branch.objects.all().order_by("name")

    context = {
        "transactions": qs[:200],  # prevent huge load
        "branches": branches,
        "active_gateway": gateway or "",
        "active_branch": branch_id or "",
        "active_status": status or "",
    }
    return render(request, "admin_panel/transactions_list.html", context)


Template templates/admin_panel/transactions_list.html:

{% extends "admin_panel/base.html" %}

{% block content %}
<div class="container-fluid">
  <h1 class="mb-4">Tüm İşlemler (Bank + Kart + Kripto)</h1>

  <form method="get" class="row g-3 mb-3">
    <div class="col-md-3">
      <label class="form-label">Site</label>
      <select name="branch" class="form-select">
        <option value="">Hepsi</option>
        {% for b in branches %}
          <option value="{{ b.id }}" {% if active_branch == b.id|stringformat:"s" %}selected{% endif %}>
            {{ b.name }}
          </option>
        {% endfor %}
      </select>
    </div>
    <div class="col-md-3">
      <label class="form-label">Gateway</label>
      <select name="gateway" class="form-select">
        <option value="">Hepsi</option>
        <option value="BANK" {% if active_gateway == "BANK" %}selected{% endif %}>Banka</option>
        <option value="CARD" {% if active_gateway == "CARD" %}selected{% endif %}>Kredi Kartı</option>
        <option value="CRYPTO" {% if active_gateway == "CRYPTO" %}selected{% endif %}>Kripto</option>
      </select>
    </div>
    <div class="col-md-3">
      <label class="form-label">Durum</label>
      <select name="status" class="form-select">
        <option value="">Hepsi</option>
        <option value="pending" {% if active_status == "pending" %}selected{% endif %}>Bekliyor</option>
        <option value="approved" {% if active_status == "approved" %}selected{% endif %}>Onaylandı</option>
        <option value="rejected" {% if active_status == "rejected" %}selected{% endif %}>Reddedildi</option>
        <option value="failed" {% if active_status == "failed" %}selected{% endif %}>Hata</option>
        <option value="expired" {% if active_status == "expired" %}selected{% endif %}>Süresi Doldu</option>
      </select>
    </div>
    <div class="col-md-3 d-flex align-items-end">
      <button type="submit" class="btn btn-primary w-100">Filtrele</button>
    </div>
  </form>

  <div class="card">
    <div class="card-body p-0">
      <table class="table table-striped mb-0">
        <thead>
          <tr>
            <th>Tarih</th>
            <th>Site</th>
            <th>Gateway</th>
            <th>Yön</th>
            <th>Kullanıcı</th>
            <th>Tutar</th>
            <th>Durum</th>
            <th>Ref</th>
          </tr>
        </thead>
        <tbody>
        {% for tx in transactions %}
          <tr>
            <td>{{ tx.created_at|date:"Y-m-d H:i" }}</td>
            <td>{{ tx.branch.name }}</td>
            <td>{{ tx.gateway }}</td>
            <td>{{ tx.direction }}</td>
            <td>{{ tx.user_name }}</td>
            <td>{{ tx.amount }} {{ tx.currency }}</td>
            <td>{{ tx.status }}</td>
            <td>{{ tx.ref_code }}</td>
          </tr>
        {% empty %}
          <tr><td colspan="8" class="text-center py-4">Kayıt yok.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}


This gives you:

A single unified table for all gateways.

Filters by site, gateway, status.

You can later add export, drilldown (click → see bank/card/crypto detail), etc.