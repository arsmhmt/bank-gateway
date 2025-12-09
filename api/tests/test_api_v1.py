import json
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

# Correct imports for your project
from branches.models import Branch, SiteGatewayConfig
from core.models import PaymentTransaction, GatewayType, User, DepositRequest
from crypto.models import CryptoWalletConfig, CryptoPayment
from core.models import BankAccount


class ApiV1TestBase(TestCase):
    def setUp(self):
        # Create a test Branch (= Site) with required user
        branch_user = User.objects.create_user(username="branch_user", password="pass1234")
        branch_user.role = User.ROLE_BRANCH
        branch_user.save()

        self.branch = Branch.objects.create(
            name="Test Site",
            site_code="TESTSITE",
            api_key="TEST_API_KEY",
            is_active=True,
            user=branch_user,
        )

        # Enable BANK + CRYPTO Gateway
        SiteGatewayConfig.objects.create(
            branch=self.branch,
            gateway=GatewayType.BANK,
            is_enabled=True,
        )
        SiteGatewayConfig.objects.create(
            branch=self.branch,
            gateway=GatewayType.CRYPTO,
            is_enabled=True,
        )

        # Create one enabled wallet
        self.crypto_wallet = CryptoWalletConfig.objects.create(
            branch=self.branch,
            coin="USDT",
            network="TRC20",
            address="TTESTADDRESS123",
            label="Test Wallet",
            is_active=True,
            is_deposit_enabled=True,
            min_deposit_amount=1,
        )

        # Create a provider and bank account so BANK gateway has an active account
        self.provider = User.objects.create_user(username="prov1", password="pass1")
        self.provider.role = User.ROLE_PROVIDER
        self.provider.save()

        BankAccount.objects.create(
            provider=self.provider,
            bank_name="Test Bank",
            account_holder="Prov",
            iban="TR000000000000000000000000",
            is_active=True,
        )

    def _auth_headers(self):
        return {"HTTP_X_API_KEY": self.branch.api_key}

    def _post_json(self, url_name, payload):
        url = reverse(url_name)
        return self.client.post(
            url,
            json.dumps(payload),
            content_type="application/json",
            **self._auth_headers(),
        )


class DepositApiTests(ApiV1TestBase):
    def test_bank_deposit_create_success(self):
        payload = {
            "gateway": "BANK",
            "external_user_id": "player123",
            "amount": 100.0,
            "currency": "TRY",
            "payment_token": "bank-deposit-001",
        }

        resp = self._post_json("api:api_deposit_create", payload)
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("data", data)

        # DepositRequest created with the payment_token
        self.assertTrue(DepositRequest.objects.filter(payment_token="bank-deposit-001").exists())

    def test_crypto_deposit_create_success(self):
        payload = {
            "gateway": "CRYPTO",
            "external_user_id": "player999",
            "amount": 50.0,
            "currency": "USDT",
            "payment_token": "crypto-deposit-001",
        }

        resp = self._post_json("api:api_deposit_create", payload)
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("data", data)

        # CryptoPayment created with payment_token
        self.assertTrue(CryptoPayment.objects.filter(payment_token="crypto-deposit-001").exists())

    def test_gateway_disabled(self):
        cfg = SiteGatewayConfig.objects.get(branch=self.branch, gateway=GatewayType.CRYPTO)
        cfg.is_enabled = False
        cfg.save()

        payload = {
            "gateway": "CRYPTO",
            "external_user_id": "player777",
            "amount": 10.0,
            "currency": "USDT",
            "payment_token": "crypto-disabled-001",
        }

        resp = self._post_json("api:api_deposit_create", payload)
        # Depending on implementation this may be 400 or 403
        self.assertIn(resp.status_code, (400, 403))
        data = resp.json()
        self.assertFalse(data.get("success"))


class TransactionStatusApiTests(ApiV1TestBase):
    def test_transaction_status_found(self):
        token = "status-test-001"
        # Create a DepositRequest to be discovered by transaction_status
        DepositRequest.objects.create(
            branch=self.branch,
            user_name="u1",
            external_user_id="ext1",
            amount=200.0,
            currency="TRY",
            provider=self.branch.user,
            payment_token=token,
            status="approved",
        )

        resp = self.client.get(reverse("api:api_transaction_status"), {"payment_token": token})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))

    def test_transaction_status_not_found(self):
        resp = self.client.get(reverse("api:api_transaction_status"), {"payment_token": "does-not-exist"})
        data = resp.json()
        self.assertFalse(data.get("success"))
        # payload may use 'error_code' or 'code' depending on utils; check both
        self.assertIn("NOT_FOUND", data.get("error_code", data.get("code", "")) or "")
