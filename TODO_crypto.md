Crypto Gateway (Manual Wallet + Ledger Mode)
Context

PaymentTransaction + GatewayType.CRYPTO are already in place.

CryptoPayment and listener scaffolds exist.

Goal: make the crypto gateway usable in production with two modes:

MANUAL – merchant uses any wallet (Metamask, Phantom, Binance, Gate.io, etc.).

LEDGER – merchant uses Ledger Nano X as cold storage (LiderPay uses xpub for deposit addresses; merchant signs withdrawals manually with Ledger).

No private keys are ever stored in LiderPay.
LiderPay only manages public data (addresses/xpub), tracking, and transaction state.

Phase C1 – Crypto Wallet Configuration Model
C1.1 Add WalletMode + CryptoWalletConfig

File: crypto/models.py

Add:

from django.db import models
from branches.models import Branch


class WalletMode(models.TextChoices):
    MANUAL = "MANUAL", "Manual External Wallet"
    LEDGER = "LEDGER", "Ledger Cold Wallet"


class CryptoWalletConfig(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="crypto_wallets",
    )
    mode = models.CharField(
        max_length=10,
        choices=WalletMode.choices,
        default=WalletMode.MANUAL,
    )

    coin = models.CharField(max_length=20)      # e.g. USDT, BTC, ETH
    network = models.CharField(max_length=20)   # e.g. TRC20, ERC20, BTC

    # Manual wallet fields (used when mode == MANUAL)
    address = models.CharField(max_length=120, blank=True)
    memo_tag = models.CharField(max_length=120, blank=True)

    # Ledger fields (used when mode == LEDGER)
    ledger_xpub = models.CharField(max_length=255, blank=True)
    derivation_index = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("branch", "coin", "network")


Run migrations.

C1.2 Wire CryptoPayment to use coin/network consistently

Ensure CryptoPayment has at least:

class CryptoPayment(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    coin = models.CharField(max_length=20)
    network = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=14, decimal_places=8)
    currency = models.CharField(max_length=10, default="USDT")  # or TRY if fiat-based
    address = models.CharField(max_length=120)
    tx_hash = models.CharField(max_length=120, blank=True, null=True)
    direction = models.CharField(max_length=10, default="IN")  # IN=deposit, OUT=withdraw
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)


(Adjust to match existing fields; don’t break migrations.)

Phase C2 – Admin UI for CryptoWalletConfig
C2.1 System Admin CRUD

Target: admin_panel (system-level configuration view)

Add a page under “Crypto Gateway”:

List all CryptoWalletConfig rows:

branch

mode

coin

network

is_active

Links/buttons to:

add new wallet config

edit existing

deactivate/reactivate

On the edit/create form, fields:

branch (dropdown)

mode (MANUAL / LEDGER)

coin, network

If mode == MANUAL:

address, memo_tag

If mode == LEDGER:

ledger_xpub, derivation_index (read-only or hidden; auto-managed)

Use conditional rendering in template to show only relevant fields based on mode (simple JS or server-side template logic).

C2.2 Branch (Site) panel read-only view

Target: site_panel

Add a “Crypto Wallets” info page:

For the current branch, list active CryptoWalletConfig rows.

Show:

mode

coin, network

address or “Ledger-managed” indicator

No edit here in v1 (editing only by system admin).

Phase C3 – Public Crypto Deposit Flow (MANUAL mode v1)
C3.1 Select the active wallet config

File: public_gateway/views_crypto.py

In the crypto_deposit view:

Resolve branch (already done).

Validate SiteGatewayConfig for GatewayType.CRYPTO.

Determine coin and network:

From query params (?coin=USDT&network=TRC20) or defaults.

Fetch:

cfg = CryptoWalletConfig.objects.filter(
    branch=branch,
    coin=coin,
    network=network,
    is_active=True,
).first()


If not found → show friendly info page / error.

If cfg.mode == WalletMode.MANUAL:

Use cfg.address (and cfg.memo_tag if set) as the deposit target.

Render deposit_base.html with:

active_gateway = "CRYPTO"

crypto_mode = "MANUAL"

deposit_address = cfg.address

memo_tag = cfg.memo_tag

C3.2 Create CryptoPayment + PaymentTransaction on form submit

For v1, crypto deposit form can ask:

user_name

amount (optional, if you want them to specify)

coin, network (hidden or fixed)

On POST:

Validate user_name, amount (if required).

Create CryptoPayment:

payment = CryptoPayment.objects.create(
    branch=branch,
    coin=coin,
    network=network,
    amount=amount,
    currency=currency,  # from API or default
    address=cfg.address,
    direction="IN",
    status="pending",
)


Create PaymentTransaction:

PaymentTransaction.objects.create(
    branch=branch,
    gateway=GatewayType.CRYPTO,
    direction="IN",
    amount=amount,
    currency=currency,
    user_name=user_name,
    status="pending",
    ref_code=str(payment.pk),
    crypto_payment=payment,
)


Show “pending” page with instructions:

Send to cfg.address on network.

Show QR.

Inform that admin will confirm.

Phase C4 – Public Crypto Deposit Flow (LEDGER mode v1)
C4.1 Derive deposit address (placeholder logic)

Still in crypto_deposit view:

If cfg.mode == WalletMode.LEDGER:

Use a temporary deterministic placeholder until a full HD-derivation lib is integrated.

Example placeholder (for development only):

derived_address = f"{cfg.ledger_xpub[:16]}-{cfg.derivation_index}"


TODO marker: replace with real HD derivation later (using xpub + index).

Use derived_address as CryptoPayment.address.

Also:

cfg.derivation_index += 1
cfg.save(update_fields=["derivation_index"])


Create CryptoPayment and PaymentTransaction same as in MANUAL mode, but address = derived_address.

Render “pending” page with:

Address

Network

QR

Info that funds go to merchant’s Ledger-controlled wallet.

Phase C5 – Crypto Withdrawal (manual confirmation)
C5.1 Model and fields

Ensure CryptoPayment supports withdrawals:

direction field: "IN" for deposits, "OUT" for withdrawals.

address:

For deposits: where user sends the funds.

For withdrawals: player’s wallet address.

tx_hash:

Filled once the merchant sends funds.

C5.2 Withdrawal request UI (site panel)

Add a crypto withdrawal request view in site_panel where:

Operator can see:

branch’s crypto withdrawal requests (direction="OUT", status="pending")

coin, network, amount, player address

For each pending withdrawal:

Merchant sends coins from their wallet (Metamask, Ledger integration, Binance, etc.).

Merchant enters tx_hash into form and clicks “Approve”.

On approve:

Set CryptoPayment.status = "approved".

Set related PaymentTransaction.status = "approved".

Save tx_hash.

Optional: add "Reject" (set status="rejected" with reason).

Phase C6 – Minimal Listener / Explorer Integration (optional v1.5)

Not required for first usable version, but keep TODO markers.

Add TODO in crypto/services.py:

check_deposit_confirmations(payment: CryptoPayment) -> None:

Will query a blockchain API by coin/network/address/amount.

If confirmed, set status="approved", notify site, update PaymentTransaction.

Add TODO in cron or management command:

python manage.py poll_crypto_deposits to run every X minutes.

Until this is implemented, deposits are manually confirmed by merchant via panel.

Phase C7 – Admin/Site UX polishing

In public templates for crypto:

Show different labels depending on crypto_mode:

MANUAL → “Use your exchange or wallet to send to this address”

LEDGER → “This wallet is protected by cold storage (Ledger).”

In admin views:

Filter CryptoWalletConfig by mode, coin, network.

Highlight “LEDGER” rows with a badge.

In PaymentTransaction list, ensure:

CRYPTO transactions display:

coin

network

tx_hash (if available)

Acceptance Criteria

System admin can:

Configure Manual crypto wallets (coin, network, address).

Configure Ledger-style wallets with ledger_xpub and auto-incrementing derivation_index.

Public /p/<code>/crypto/deposit/:

Uses CryptoWalletConfig to determine:

Whether crypto is available for that branch.

Which mode is active (MANUAL / LEDGER).

Creates CryptoPayment + PaymentTransaction on submit.

Shows appropriate address + instructions.

Withdrawals:

Are tracked via CryptoPayment(direction="OUT") + PaymentTransaction.

Are manually marked approved by merchant/admin with tx_hash.

No private keys or seeds are ever stored in the database.

Ledger Nano X never directly connects to the backend; only its public data (xpub / derived addresses) is used.


we can support both:

Manual wallets (Metamask, Phantom, Binance, Gate, etc.)

Ledger-backed cold storage

But for Ledger, we still won’t plug it directly into your backend. We’ll design it so:

Backend uses public info (xpub / public addresses)

Merchant uses Ledger only to sign withdrawals on their side

Let’s design both modes clearly.

1️⃣ Mode A – Manual Wallet Mode (Metamask, CEX, etc.)

Goal:
Merchant uses any wallet (Metamask, Phantom, Binance, Gate.io) to receive deposits and send payouts. LiderPay just orchestrates and tracks.

a) Config model

Add something like:

# crypto/models.py

class WalletMode(models.TextChoices):
    MANUAL = "MANUAL", "Manual External Wallet"
    LEDGER = "LEDGER", "Ledger Cold Wallet"


class CryptoWalletConfig(models.Model):
    branch = models.ForeignKey("branches.Branch", on_delete=models.CASCADE, related_name="crypto_wallets")
    mode = models.CharField(max_length=10, choices=WalletMode.choices, default=WalletMode.MANUAL)

    coin = models.CharField(max_length=20)      # e.g. USDT, BTC, ETH
    network = models.CharField(max_length=20)   # e.g. TRC20, ERC20, BTC

    # Manual wallet fields:
    address = models.CharField(max_length=120)  # plain address
    memo_tag = models.CharField(max_length=120, blank=True)  # for exchanges if needed

    is_active = models.BooleanField(default=True)

b) Admin UI (System admin / Site)

System admin:

Defines allowed coins + networks

Site (branch) admin:

Chooses “Manual wallet”

Pasts address for each coin/network they want to accept

Optional memo/tag for CEX like Binance / Gate

c) Deposit flow in MANUAL mode

User opens /p/<code>/crypto/deposit/

System checks CryptoWalletConfig for this branch, coin & network.

UI shows:

Address

Network

Memo/Tag if any

QR code

User sends coins from Metamask / Binance / etc.

V1 confirmation options:

Simple: Site admin checks in their wallet/explorer and manually clicks “Confirm deposit” in LiderPay → sets CryptoPayment.status = approved.

Advanced later: auto-check via blockchain API using the configured address.

d) Withdrawal in MANUAL mode

User requests withdraw → CryptoPayment with status pending.

Admin sees list of withdrawal requests.

Admin sends coins from Metamask/Binance to player’s address.

Admin pastes tx hash into LiderPay and marks as approved.

👉 No private keys on your server.
👉 Works with any wallet.
👉 Zero Ledger complexity.

2️⃣ Mode B – Ledger Mode (Merchant’s Nano X, NOT on your backend)

Here the key rule:

Ledger stays in customer’s hands. Your backend only uses public information.

We’ll design:

Backend: uses xpub / public addresses to generate and track deposits

Merchant: uses Ledger to sign withdrawals manually

a) Ledger-related config

Extend CryptoWalletConfig:

class CryptoWalletConfig(models.Model):
    branch = models.ForeignKey("branches.Branch", on_delete=models.CASCADE, related_name="crypto_wallets")
    mode = models.CharField(max_length=10, choices=WalletMode.choices)

    coin = models.CharField(max_length=20)
    network = models.CharField(max_length=20)

    # Manual wallet fields:
    address = models.CharField(max_length=120, blank=True)
    memo_tag = models.CharField(max_length=120, blank=True)

    # Ledger fields:
    ledger_xpub = models.CharField(max_length=255, blank=True)       # extended public key or similar
    derivation_index = models.PositiveIntegerField(default=0)        # next index to use

    is_active = models.BooleanField(default=True)

b) System Admin UI for Ledger

In System Admin → Crypto Gateway → Ledger setup:

For each branch:

Choose Mode = LEDGER

For coin/network (e.g. BTC, USDT-TRC20):

Paste xpub or public root (depending on how you standardize this)

Show:

“Next address index: N”

Preview first few derived addresses

You also add help text:

“Export your public key / xpub from Ledger and paste it here. DO NOT paste seed or private keys.”

c) Deposit flow in LEDGER mode

User goes to /p/<code>/crypto/deposit/?coin=USDT&network=TRC20

Backend looks up:

cfg = CryptoWalletConfig.objects.get(branch=branch, coin="USDT", network="TRC20", mode=LEDGER)


Backend derives a new address from ledger_xpub + derivation_index.

You can use a Python HD wallet lib for this later.

Save in CryptoPayment:

payment = CryptoPayment.objects.create(
    branch=branch,
    coin="USDT",
    network="TRC20",
    amount=amount,
    address=derived_address,
    status="pending",
)
cfg.derivation_index += 1
cfg.save(update_fields=["derivation_index"])


Show address + QR to user.

Confirm deposit:

V1: manual confirmation by merchant (they check Ledger/Explorer).

Later: polling blockchain APIs using these derived addresses.

d) Withdrawal flow in LEDGER mode

For v1 (simple, safe):

Player requests withdrawal.

LiderPay creates CryptoPayment (OUT) with amount + player address.

Admin sees list of pending withdrawals in crypto panel.

Admin manually uses Ledger + their wallet (Ledger Live / Metamask Ledger integration) to send coins from the Ledger-managed wallet to player.

Admin pastes tx hash into LiderPay and marks withdrawal approved.

In future advanced version, you can:

Let LiderPay prepare an unsigned raw transaction (UTXO-based or EVM-based).

Merchant imports it into their local signer with Ledger.

Merchant signs and returns signed tx to LiderPay to broadcast.

But for now, manual is enough and much simpler.

3️⃣ How this fits into your current system

CryptoWalletConfig is the bridge between:

Mode A: “any wallet” (Metamask, CEX, etc.)

Mode B: Ledger xpub-mode

CryptoPayment + PaymentTransaction stay unchanged logically:

They always store:

coin, network, amount, currency

address (where user pays or receives)

tx_hash

status

Public URLs /p/<code>/crypto/deposit/:

Look up active CryptoWalletConfig for that branch + coin + network.

If mode == MANUAL → use static address.

If mode == LEDGER → derive new address from ledger_xpub.

4️⃣ Which one should we implement first?

Given everything else you have on your plate, I'd do:

Implement Mode A (Manual wallets) fully in v1

This covers Metamask, Phantom, Binance, Gate.io.

No Ledger-related complexity.

Crypto gateway becomes usable immediately.

Add Mode B (Ledger) as a configuration extension

You add fields for ledger_xpub and derivation_index.

Derivation & listener logic can be added gradually.

Ledger is used exactly the way it’s intended: offline cold storage.