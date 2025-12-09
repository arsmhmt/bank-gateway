Gateway Management (Bank / Card / Crypto)
Context
Current state:


Admin Panel (/yonetim/dashboard/): shows aggregate stats and commission tables, but no per-gateway overview or controls.


Site Panel (/site/dashboard/): focused on bank flows; crypto wallets are only visible on /site/crypto-wallets/, card status is invisible.


SiteGatewayConfig and CryptoWalletConfig already exist; PaymentTransaction is gateway-aware.


Goal:


Give owners (admin panel) a clear multi-gateway control center.


Give branches (site panel) a quick view of bank/card/crypto status + public URLs.


Reuse existing models wherever possible.



G1 – Admin Dashboard: Gateway Overview Cards
Files: admin_panel/views.py, templates/admin_panel/dashboard.html
G1.1 View: gather per-gateway stats


In the admin dashboard view:


Import SiteGatewayConfig, PaymentTransaction, GatewayType, timezone.


Compute for each gateway (BANK, CARD, CRYPTO):


enabled_branches: count of SiteGatewayConfig with is_enabled=True.


today_volume_in: sum of PaymentTransaction.amount for:


gateway=<gateway>


direction="IN"


created_at = today




pending_count: count of PaymentTransaction with:


gateway=<gateway>


status="pending"






For crypto:


Also compute a simple listener status string (placeholder):


"TRC20 listener: ACTIVE" if setting CRYPTO_TRON_EXPLORER_API_URL is set.


"TRC20 listener: DISABLED" otherwise.






Pass a gateway_overview dict into context:
context["gateway_overview"] = {
    "BANK": {...},
    "CARD": {...},
    "CRYPTO": {...},
}





G1.2 Template: render 3 cards


In dashboard.html, add a “Gateway Overview” row:


Three cards: Bank, Card, Crypto.


Each card shows:


Enabled branches


Today’s volume


Pending count




Crypto card additionally shows the listener status line.


Each card includes a “Manage” button linking to:


Bank: existing bank management page (if any) or # placeholder.


Card: /yonetim/gateways/ with gateway=CARD.


Crypto: /yonetim/crypto/overview/.







G2 – Admin: Branch × Gateway Control Matrix
Files: admin_panel/views.py, admin_panel/urls.py, templates/admin_panel/gateways_matrix.html
G2.1 URL + view: /yonetim/gateways/


Add URL pattern for admin_panel:gateways_matrix.


View responsibilities:


Query all branches.


Pre-fetch SiteGatewayConfig for all branches and gateways into a dict:
configs = SiteGatewayConfig.objects.all()
# map (branch_id, gateway) -> config



On POST, allow toggling is_enabled for a given branch + gateway:


Expect branch_id + gateway in POST.


Flip is_enabled and redirect back to the same page.




Pass to template:


branches


matrix mapping (branch.id, gateway) → SiteGatewayConfig instance.






G2.2 Template: matrix table


Table headers: Site / Bank / Card / Crypto / Actions.


For each branch row:


Show branch name.


For each gateway:


Render a small ON/OFF badge or switch based on is_enabled.


Clicking the toggle submits a small form to POST and flip the state.




“Configure” action links to detailed branch config:


/yonetim/gateways/<branch_id>/







G3 – Admin: Branch Gateway Config Page
Files: admin_panel/views.py, admin_panel/urls.py, templates/admin_panel/gateway_branch_detail.html
G3.1 URL + view: /yonetim/gateways/<branch_id>/


Add URL pattern for admin_panel:gateway_branch_detail.


View:


Fetch the branch.


Fetch (or create if missing) SiteGatewayConfig for each gateway.


Fetch any CryptoWalletConfig for this branch.


(Optional) Fetch/prepare CardPspConfig if model exists or is added later.


Handle a simple POST to toggle is_enabled per gateway or update simple fields.




Template context:


branch


site_gateway_configs (by gateway)


crypto_wallets list


card_psp_config (optional)




G3.2 Template layout


Heading: “Gateway Configuration – {{ branch.name }}”


Sections:


Bank Gateway


Enabled checkbox (bound to SiteGatewayConfig for BANK).


Link to any existing bank account / provider management pages.




Card Gateway


Enabled checkbox.


Display PSP info (merchant_id, mode TEST/LIVE) if available.




Crypto Gateway


Enabled checkbox.


Table of CryptoWalletConfig rows:


Mode (MANUAL/LEDGER)


Coin/network


Address or truncated xPub


Active status


“Edit” link to existing wallet edit page.









G4 – Admin: Crypto Overview Page
Files: admin_panel/views.py, admin_panel/urls.py, templates/admin_panel/crypto_overview.html
G4.1 URL + view: /yonetim/crypto/overview/


Add URL pattern admin_panel:crypto_overview.


View:


Query all CryptoWalletConfig (select_related branch).


Optionally, compute:


Last successful listener run timestamp (if a CronStatus or similar model exists; otherwise, skip or use a placeholder).




For each wallet, compute:


last_deposit_at: the latest CryptoPayment.created_at with direction="IN" for that (branch, coin, network).






Pass to template:


wallets


Optional listener_status string.




G4.2 Template


Section: “TRC20 Listener Status”


Show active/disabled based on presence of CRYPTO_TRON_EXPLORER_API_URL and mention polling frequency (5 min).




Table of wallets:


Branch


Mode (MANUAL/LEDGER)


Coin / Network


Active


Address (shortened) or xPub suffix


Last deposit date/time





G5 – Site Dashboard: Gateway Status Card
Files: site_panel/views.py, templates/site_panel/dashboard.html
G5.1 View: augment branch dashboard context


In /site/dashboard/ view:


Resolve branch from request.user.


Load SiteGatewayConfig for that branch.


Load primary CryptoWalletConfig (e.g., first active one, or the USDT/TRC20 one).


Compute per-gateway stats for today using PaymentTransaction filtered by:


branch=branch


gateway


direction and status.






Build a small gateway_status dict:
context["gateway_status"] = {
    "BANK": {
        "enabled": ...,
        "today_in_count": ...,
        "today_out_count": ...,
    },
    "CARD": {...},
    "CRYPTO": {
        "enabled": ...,
        "mode": "MANUAL"/"LEDGER"/None,
        "coin": "USDT",
        "network": "TRC20",
        "last_deposit_at": ...,
    },
}



G5.2 Template: “Gateway Status” card


Add a card named “Gateway Status” to /site/dashboard.html:


For each gateway:


Show ON/OFF badge.


Show small stats (e.g., “Today: 5 deposits / 2 withdrawals”).


For crypto, show mode and coin/network if enabled.




Provide quick links:


Bank: “View Bank Deposits”


Card: “View Card Transactions” (placeholder until implemented)


Crypto: “View Crypto Wallets” → /site/crypto-wallets/
“View Crypto Transactions” → crypto transaction list page (if exists).







G6 – Site Dashboard: Public Payment Links Block
Files: site_panel/views.py, templates/site_panel/dashboard.html
G6.1 View: compute URLs


In /site/dashboard/ view, add:
public_urls = {
    "BANK_DEPOSIT": f"{PUBLIC_BASE_URL}/p/{branch.site_code}/bank/deposit/",
    "CARD_DEPOSIT": f"{PUBLIC_BASE_URL}/p/{branch.site_code}/card/deposit/",
    "CRYPTO_DEPOSIT": f"{PUBLIC_BASE_URL}/p/{branch.site_code}/crypto/deposit/",
}



PUBLIC_BASE_URL can come from settings or be derived.




Pass public_urls to context.


G6.2 Template: link block


Add a “Public Payment Links” block to /site/dashboard.html:


For each enabled gateway only:


Show label + the URL in a readonly input.


Add “Copy” button (small JS navigator.clipboard.writeText()).




Add a small note:


“Use these URLs in your cashier/payment page or Betco configuration.”







G7 – Site Panel: Crypto / Card Settings Pages
Crypto: /site/crypto-wallets/ (already exists)


Enhance the existing template to show:


Mode (MANUAL/LEDGER) clearly.


For MANUAL: address + network info + warning text.


For LEDGER: xPub suffix + “Ledger cold wallet” note.




Add a link back to /site/dashboard/.


Card: new /site/card-settings/ (optional v1)


View shows read-only card PSP info for the current branch:


Provider name


Mode (TEST/LIVE)


Merchant ID


Active status




Link this page from the Site dashboard “Gateway Status” card under Card.



G8 – Optional: CardPspConfig model
If not yet present, define:
class CardPspConfig(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    provider_name = models.CharField(max_length=50)  # e.g. PAYTR, IYZICO
    merchant_id = models.CharField(max_length=100)
    terminal_id = models.CharField(max_length=100, blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    mode = models.CharField(
        max_length=10,
        choices=[("TEST", "Test"), ("LIVE", "Live")],
        default="TEST",
    )



Use this in G3 (branch gateway config page) and G7 (site card settings).



Implementation order suggestion:


G1 (Admin dashboard cards)


G2 + G3 (Admin gateway control + branch detail)


G4 (Crypto overview)


G5 + G6 (Site dashboard status + public URLs)


G7 (Crypto/Card settings polish)


G8 (CardPspConfig) if needed for real card integration.




I’ll give you a clear feature spec you can hand to Codex (or yourself) for:

Admin Panel /yonetim/dashboard/ (owner view)

Site Panel /site/dashboard/ (branch operator view)

UI placement decisions

Data / model usage (what’s already there vs what’s missing)

1️⃣ Concepts we’ll lean on

You already have:

SiteGatewayConfig

branch

gateway (BANK, CARD, CRYPTO)

is_enabled

CryptoWalletConfig

branch, coin, network, mode (MANUAL/LEDGER), address, ledger_xpub, is_active, etc.

Card PSP config (likely something like CardMerchantConfig – or you can add it)

PaymentTransaction with gateway + direction + status

We won’t invent crazy new models; we’ll mostly surface what you already track + add 1–2 small config models for card PSP if needed.

2️⃣ Admin Panel – what the OWNER should see / control
2.1 Dashboard layout

On /yonetim/dashboard/, keep your existing aggregate stats, but add a new section:

“Gateway Overview” – one card per gateway + a quick per-branch status table.

A. Gateway summary cards (top row)

Three cards:

Bank Gateway

Enabled branches: SiteGatewayConfig(gateway=BANK, is_enabled=True).count()

Today’s volume: sum of PaymentTransaction for BANK, direction=IN, today

Pending approvals: pending bank deposits/withdrawals

Card Gateway

Enabled branches count

Today’s card volume / transactions

PSP status (UP/DOWN/DEGRADED)

Crypto Gateway

Enabled branches count

Today’s crypto volume (USDT equivalent)

Auto-confirm status: “TRC20 listener: ACTIVE” / “DISABLED”

Each card links to a more detailed “Gateway Control” page for that gateway.

2.2 Per-branch gateway control (Admin)

New page:

/yonetim/gateways/ → “Gateway Control (Branches)”

Table:

Site / Branch	Bank	Card	Crypto	Actions
Lacosbet	ON	OFF	ON	[Configure]
DemoBet	ON	ON	OFF	[Configure]

Each gateway column uses data from SiteGatewayConfig.

Toggles:

Click ON/OFF to flip is_enabled for that branch/gateway (with small POST).

“Configure” links to a branch-specific page:

/yonetim/gateways/<branch_id>/

Branch-specific gateway config page

For each branch:

Show branch name + basic info.

Section Bank Gateway:

Enabled? (checkbox linked to SiteGatewayConfig)

Link to bank account limits and provider assignments (existing bank logic).

Section Card Gateway:

Enabled?

Card PSP merchant ID / terminal ID / mode (test/live)

Optional: limit per transaction / per day

Section Crypto Gateway:

Enabled?

Show their CryptoWalletConfig rows:

Mode (MANUAL/LEDGER)

Coin/network

Address or “Managed by Ledger (xPub ending in …1234)”

“Edit” link

This page is admin-only (OWNER or system admin).

2.3 Crypto-specific admin view

New page:

/yonetim/crypto/overview/

Content:

Listener status:

Last run time of poll_crypto_deposits (you can store this in a small log table or just show from a CronStatus model later).

Result: “OK (last run 2 min ago)” or “Warning (no runs in 30+ min)”.

Wallet list:

Branch	Mode	Coin/Network	Active	Address / xPub	Last Deposit
Lacos	LEDGER	USDT/TRC20	YES	xpub…1234	2025-12-01
Demo	MANUAL	USDT/TRC20	YES	TAbc…xyz	—

Data source: CryptoWalletConfig.

This screen is mostly read-only, with links to edit each CryptoWalletConfig.

2.4 Card PSP health

If you don’t have a model yet, you can introduce:

class CardPspConfig(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    provider_name = models.CharField(max_length=50)  # e.g. PAYTR, IYZICO
    merchant_id = models.CharField(max_length=100)
    terminal_id = models.CharField(max_length=100, blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    mode = models.CharField(max_length=10, choices=[('TEST','Test'),('LIVE','Live')], default='TEST')


Admin dashboard card:

“Card Gateway”

Show:

Live PSP configs count

mode distribution (how many in TEST vs LIVE)

A status string like: “3 branches live, 1 in test”

Later you can add real health pings.

3️⃣ Site Panel – what a BRANCH operator should see

Right now /site/dashboard/ is mainly bank-focused. Let’s make it “Payment control center” for that branch.

3.1 Gateway Overview card

On /site/dashboard/, add a “Gateway Status” card for the branch.

Card layout:

Bank:

Status: ON / OFF (SiteGatewayConfig)

Today: X deposits / Y withdrawals

Link: “Go to Bank Deposits”

Card:

Status: ON / OFF

Today: card deposits count + volume

Link: “Go to Card Transactions”

Crypto:

Status: ON / OFF

If ON:

Mode: MANUAL or LEDGER from CryptoWalletConfig

Main coin/network: e.g. USDT/TRC20

Last deposit time / amount

Link: “Go to Crypto Wallets” and “View Crypto Transactions”

(To keep it small, you can show only the primary CryptoWalletConfig per branch, or the first active one.)

3.2 Shortcuts to public URLs

Below or inside the same card, show:

“Public Payment Links”

For enabled gateways only:

Bank deposit URL

Crypto deposit URL

Card deposit URL

Each with:

Copy button

Small label “Use this in your Betco cashier/settings”

Data comes from:

request.branch.site_code

Static route patterns (/p/<code>/bank/deposit/, etc.)

3.3 Crypto info block in Site Panel

Separate page already exists: /site/crypto-wallets/.

Enhance it with:

Current wallet configs table:

Mode (MANUAL/LEDGER)

Coin/network

Address/xPub preview

Active toggle

Info banner:

If MANUAL: “You are using a static wallet address. Change carefully; old addresses remain valid but new users will see the new address.”

If LEDGER: “Deposit addresses are derived from your Ledger public key. Do not change your Ledger account without updating xPub.”

Also link from /site/dashboard/ with a button “Manage Crypto Wallet”.

3.4 Card gateway info block in Site Panel

Add /site/card-settings/:

Show PSP provider name, merchant_id, mode (TEST/LIVE).

Show current per-transaction/per-day limits if you implement these fields.

Show activation status for this branch.

This is mostly informational; real toggles remain admin-side.

4️⃣ UI Placement Summary

To answer your explicit questions:

Admin dashboard expectations?

New “Gateway Overview” section on /yonetim/dashboard/:

3 cards (Bank, Card, Crypto) with high-level stats.

New “Gateway Control (Branches)” page:

Matrix of branches × gateways with enable/disable toggles.

New “Crypto Overview” page:

Wallet/XPub list + listener status.

Site dashboard expectations?

Add a “Gateway Status” card:

Per-gateway ON/OFF + minimal stats.

Add a “Public payment links” block with copy buttons.

Keep deep config pages separate:

/site/crypto-wallets/

/site/card-settings/

Bank pages as you already have.

UI placement: sections vs tabs vs pages?

Dashboard: summary cards only (no heavy forms).

Config: dedicated pages:

Admin: /yonetim/gateways/, /yonetim/gateways/<branch_id>/, /yonetim/crypto/overview/

Site: /site/crypto-wallets/, /site/card-settings/

Data requirements:

Use existing models wherever possible:

SiteGatewayConfig → on/off state per gateway + per branch.

CryptoWalletConfig → crypto mode + wallet/xPub summary.

PaymentTransaction → stats per gateway/direction/status.

Only new data you may want:

CardPspConfig model per branch (if not already there).

Optional CronStatus or ListenerStatus model to track last successful poll_crypto_deposits run.

while we’re implementing UI elements, we should lock down the UI rules, hierarchy, and component structure so every new section you add (Admin + Site dashboards) stays consistent, clean, and scalable.

Below is what I recommend before touching HTML/CSS:

✅ 1. Define the UI Architecture (what belongs where)

Your panels already follow a structure:

Admin Panel → system-wide controls + insights

Site Panel → branch operator tools

Provider Panel → bank account provider tools

Now we’re adding Card + Crypto.
We must avoid UI clutter or confusing navigation.
So:

✔ Admin Panel = MANAGEMENT panel

Admin sees:

Gateway overview stats

Toggle ON/OFF gateways for branches

Wallet/xPub info

PSP (card) configurations

Crypto listener status

High-level transaction summaries

Admin never initiates transactions — only config & monitoring.

✔ Site Panel = OPERATIONS panel

Site operator sees:

Today’s activity

Gateway status for that branch

Deposit/withdraw queues

Wallet settings (crypto)

PSP settings (read-only)

Public URLs (copy-ready)

Site operators do read/write operations:

Approve withdrawals

Configure crypto wallets

Fetch public payment URLs

Manage only their own branch configs

✅ 2. UI Layout Rules (consistency across all panels)
🔹 Dashboard sections must follow the same structure everywhere:

Each dashboard should display:

Top stats row

Today’s deposits / withdrawals

Gateway activity summary

Commission summary (if applicable)

Gateway Status row

3 cards: Bank / Card / Crypto

ON/OFF indicator

Quick stats

Link to management page

Quick Actions / Links row

Public URLs

Wallet settings

PSP settings

Provider actions (bank only)

This keeps both Admin & Site dashboards visually aligned.

✅ 3. UI Component Library (so Codex builds consistent blocks)

We define reusable components:

🟦 Card: Gateway Status Block

Used in admin and site.

-----------------------------------------
| Crypto Gateway                        |
-----------------------------------------
| Status: ✔ Enabled                     |
| Mode: Ledger Cold Wallet              |
| Coin: USDT (TRC20)                    |
| Last Deposit: 18:22 – 32 USDT         |
-----------------------------------------
| [Manage Crypto]     [View Transactions]
-----------------------------------------

🟦 Card: Public URL Block
-----------------------------------------
| Public Deposit URL (Crypto)           |
-----------------------------------------
| https://lider-pay.com/p/ABC/crypto... |
| [Copy]                                 |
-----------------------------------------

🟦 Table: Gateway Matrix (Admin)
Branch        Bank    Card    Crypto    Actions
-----------------------------------------------------
Lacosbet      ON      OFF     ON        [Configure]
DemoBet       ON      ON      OFF       [Configure]

🟦 Wallet Row (CryptoWalletConfig)
Mode: LEDGER
Coin/Network: USDT / TRC20
Address/XPub: xpub...98as (click to expand)
Status: Active ✔
[Edit]

✅ 4. UX Rules (to avoid confusion or runtime issues)

These are important so customers understand what settings do.

✔ Rule 1 — Gateway status indicators must reflect SiteGatewayConfig

Every card that says Enabled / Disabled MUST come from:

SiteGatewayConfig(branch, gateway).is_enabled


No “hidden logic” anywhere else.

✔ Rule 2 — Crypto Mode must show MANUAL vs LEDGER clearly

If crypto enabled:

Show LEDGER badge if ledger_xpub exists

Show MANUAL badge otherwise

If LEDGER is chosen but xPub missing → show an error badge

Avoid misconfiguration.

✔ Rule 3 — Public URLs visible only when gateway enabled

For example:

If Crypto disabled → don’t even show:

https://lider-pay.com/p/<code>/crypto/deposit/

✔ Rule 4 — Admin side actions must never break Site operator workflow

Admins toggle gateway availability
Branches manage their own operations

No overlap.

✔ Rule 5 — Error states must be visually obvious

Examples:

Crypto enabled but no wallet configured → RED WARNING CARD

Card PSP in test mode → Yellow badge “TEST MODE”

Crypto listener off → Orange badge “Listener Inactive”

This prevents runtime misconfigurations.

✅ 5. Developer Implementation Roadmap (UI only)

Codex can implement UI in this order:

🔸 Step 1 — Admin Dashboard UI

Add:

Gateway Overview section (3 cards)

Buttons linking to:

/yonetim/gateways/

/yonetim/crypto/overview/

/yonetim/card/overview/ (placeholder)

🔸 Step 2 — Admin Gateway Matrix Page

Implement the Branch × Gateway table with toggles.

🔸 Step 3 — Admin Branch Gateway Detail Page

Sections:

Bank Gateway

Card Gateway

Crypto Gateway (with wallet list)

🔸 Step 4 — Admin Crypto Overview Page

Wallet table + listener status block.

🔸 Step 5 — Site Dashboard UI

Add:

Gateway Status card (3 sub-blocks)

Public Payment URL block

Quick links:

Bank Deposits

Card Transactions

Crypto Wallets

Crypto Transactions

🔸 Step 6 — Site Crypto Wallets Page Enhancements

Add clear mode badges + warnings.

🔸 Step 7 — Site Card Settings Page (simple read-only)
✅ 6. Optional but recommended UI refinements
1. Add a “Mode Badge” system:

“LEDGER COLD WALLET”

“MANUAL STATIC ADDRESS”

“TEST MODE”

“LIVE MODE”

“GATEWAY DISABLED”

2. Add a tooltip system for explanations (Codex can implement)

Useful for:

xPub meaning

card PSP credentials

gateway activation logic

3. Add color-coded gateway icons

Makes the UI instantly intuitive.