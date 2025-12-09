from decimal import Decimal
import uuid
from random import randint, choice

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.models import (
    BankAccount,
    DepositRequest,
    WithdrawalRequest,
    PaymentTransaction,
    Client,
)
from branches.models import Branch
from crypto.models import CryptoWalletConfig, CryptoPayment

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo site, teminci, bank/crypto accounts and transactions."

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) Create demo provider (teminci)
        demo_provider, _ = User.objects.get_or_create(
            username="demo_teminci",
            defaults={
                "email": "demo.teminci@liderpay.com",
                "role": User.ROLE_PROVIDER,
                "is_active": True,
            },
        )

        # 1b) Create a site user and branch for demo site (Branch requires a user)
        demo_site_user, _ = User.objects.get_or_create(
            username="demo_site",
            defaults={
                "email": "demo.site@liderpay.com",
                "role": User.ROLE_BRANCH,
                "is_active": True,
            },
        )

        # 2) Create demo branch / site
        demo_branch, created = Branch.objects.get_or_create(
            site_code="DEMO-001",
            defaults={
                "name": "Demo Site",
                "user": demo_site_user,
                "api_key": "DEMO_API_KEY_001",
                "is_active": True,
                "callback_url": "https://example.com/demo-callback",
            },
        )
        if not created:
            # ensure branch has a user assigned
            if demo_branch.user_id != demo_site_user.id:
                demo_branch.user = demo_site_user
                demo_branch.save()

        # 3) Enable BANK + CRYPTO gateways for demo site
        from branches.models import SiteGatewayConfig as _SiteGatewayConfig

        for gateway in ("BANK", "CRYPTO"):
            _SiteGatewayConfig.objects.get_or_create(
                branch=demo_branch,
                gateway=gateway,
                defaults={"is_enabled": True},
            )

        # 4) Bank account for demo provider
        bank_account, _ = BankAccount.objects.get_or_create(
            provider=demo_provider,
            iban="TR00000000000000000000000000",
            defaults={
                "bank_name": "Demo Bank",
                "account_holder": "Demo Teminci",
                "is_active": True,
                "account_limit": Decimal("500000.00"),
            },
        )

        # 5) Crypto wallet for demo site
        wallet, _ = CryptoWalletConfig.objects.get_or_create(
            branch=demo_branch,
            coin="USDT",
            network="TRC20",
            defaults={
                "label": "Demo USDT Cüzdanı",
                "is_active": True,
                "is_deposit_enabled": True,
                "min_deposit_amount": Decimal("5.00"),
                "address": "TDEMOADDRESS1234567890",
            },
        )

        # 5b) Demo client used for withdrawals
        demo_client, _ = Client.objects.get_or_create(
            name="Demo Client",
            defaults={
                "contact_info": "Demo client for seeded transactions",
                "deposit_commission": Decimal("0.00"),
                "withdraw_commission": Decimal("0.00"),
                "api_key": f"DEMO_CLIENT_{uuid.uuid4().hex[:8]}",
            },
        )

        STATUSES = ["pending", "approved", "rejected"]

        # 6) Create some bank deposits (mix of statuses)
        for i in range(15):
            amount = Decimal(randint(100, 3000))
            status = choice(STATUSES)
            dep = DepositRequest.objects.create(
                branch=demo_branch,
                provider=demo_provider,
                bank_account=bank_account,
                user_name=f"demo_user_{i}",
                amount=amount,
                status=status,
                submitted_at=timezone.now(),
            )
            PaymentTransaction.objects.create(
                branch=demo_branch,
                gateway="BANK",
                direction=PaymentTransaction.DIRECTION_IN,
                status=status,
                amount=amount,
                currency="TRY",
                user_name=dep.user_name,
                ref_code=f"ref-{uuid.uuid4().hex[:12]}",
            )

        # 7) A few bank withdrawals
        for i in range(5):
            amount = Decimal(randint(100, 2000))
            status = choice(["pending", "approved"])
            wd = WithdrawalRequest.objects.create(
                branch=demo_branch,
                provider=demo_provider,
                user_name=f"demo_user_wd_{i}",
                iban="TR00000000000000000000000000",
                amount=amount,
                client=demo_client,
                status=status,
                submitted_at=timezone.now(),
            )
            PaymentTransaction.objects.create(
                branch=demo_branch,
                gateway="BANK",
                direction=PaymentTransaction.DIRECTION_OUT,
                status=status,
                amount=amount,
                currency="TRY",
                user_name=wd.user_name,
                ref_code=f"ref-{uuid.uuid4().hex[:12]}",
            )

        # 8) Crypto deposits
        for i in range(10):
            amount = Decimal(randint(10, 200))
            status = choice(["pending", "approved"])
            pay = CryptoPayment.objects.create(
                branch=demo_branch,
                user_name=f"demo_crypto_{i}",
                coin="USDT",
                network="TRC20",
                address=wallet.address,
                amount=amount,
                currency="USDT",
                direction=CryptoPayment.DIRECTION_IN,
                status=status,
                payment_token=f"demo-crypto-{i}-{uuid.uuid4().hex[:6]}",
            )
            PaymentTransaction.objects.create(
                branch=demo_branch,
                gateway="CRYPTO",
                direction=PaymentTransaction.DIRECTION_IN,
                status=status,
                amount=amount,
                currency="USDT",
                user_name=pay.user_name,
                ref_code=f"ref-{uuid.uuid4().hex[:12]}",
                crypto_payment=pay,
            )

        # 9) A few crypto withdrawals
        for i in range(3):
            amount = Decimal(randint(5, 80))
            status = choice(["pending", "approved"])
            pay = CryptoPayment.objects.create(
                branch=demo_branch,
                user_name=f"demo_crypto_wd_{i}",
                coin="USDT",
                network="TRC20",
                address=wallet.address,
                amount=amount,
                currency="USDT",
                direction=CryptoPayment.DIRECTION_OUT,
                status=status,
                payment_token=f"demo-crypto-wd-{i}-{uuid.uuid4().hex[:6]}",
            )
            PaymentTransaction.objects.create(
                branch=demo_branch,
                gateway="CRYPTO",
                direction=PaymentTransaction.DIRECTION_OUT,
                status=status,
                amount=amount,
                currency="USDT",
                user_name=pay.user_name,
                ref_code=f"ref-{uuid.uuid4().hex[:12]}",
                crypto_payment=pay,
            )

        self.stdout.write(self.style.SUCCESS("Demo data seeded for DEMO-001."))
