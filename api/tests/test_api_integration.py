from django.test import TestCase, Client
from django.urls import reverse
from core.models import User, BankAccount, PaymentTransaction
from branches.models import Branch, SiteGatewayConfig
from core.models import GatewayType
from crypto.models import CryptoWalletConfig


class ApiIntegrationTests(TestCase):
    def setUp(self):
        # provider (bank account owner)
        self.provider = User.objects.create_user(username="prov1", password="pass", role=User.ROLE_PROVIDER)
        # Bank account
        self.bank_account = BankAccount.objects.create(
            provider=self.provider,
            bank_name="Test Bank",
            account_holder="Provider",
            iban="TR000000000000000000000000",
            is_active=True,
        )

        # Branch user and branch
        self.branch_user = User.objects.create_user(username="branch1", password="pass", role=User.ROLE_BRANCH)
        self.branch = Branch.objects.create(
            name="Test Branch",
            domain="example.com",
            user=self.branch_user,
            callback_url="https://example.com/cb/",
        )

        # Enable BANK and CRYPTO for branch
        SiteGatewayConfig.objects.create(branch=self.branch, gateway=GatewayType.BANK, is_enabled=True)
        SiteGatewayConfig.objects.create(branch=self.branch, gateway=GatewayType.CRYPTO, is_enabled=True)

        # Simple crypto wallet
        CryptoWalletConfig.objects.create(
            branch=self.branch,
            mode="MANUAL",
            coin="USDT",
            network="TRC20",
            address="TEXAMPLEADDRESS",
            is_active=True,
            is_deposit_enabled=True,
        )

        self.client = Client()
        self.api_key = self.branch.api_key

    def test_bank_deposit_create(self):
        url = reverse('api:api_deposit_create')
        payload = {
            "gateway": "BANK",
            "external_user_id": "player123",
            "amount": 100.00,
            "currency": "TRY",
        }
        resp = self.client.post(url, data=payload, content_type='application/json', HTTP_X_API_KEY=self.api_key)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertIn('data', data)
        self.assertIn('payment_token', data['data'])
        self.assertIn('deposit_id', data['data'])

    def test_crypto_deposit_create(self):
        url = reverse('api:api_deposit_create')
        payload = {
            "gateway": "CRYPTO",
            "external_user_id": "player123",
            "amount": 50.0,
            "currency": "USDT",
        }
        resp = self.client.post(url, data=payload, content_type='application/json', HTTP_X_API_KEY=self.api_key)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertIn('data', data)
        self.assertIn('payment_token', data['data'])
        self.assertIn('crypto_payment_id', data['data'])

    def test_transaction_status(self):
        # Create a bank deposit via API to get a payment_token
        create_url = reverse('api:api_deposit_create')
        payload = {
            "gateway": "BANK",
            "external_user_id": "playerABC",
            "amount": 77.0,
            "currency": "TRY",
        }
        resp = self.client.post(create_url, data=payload, content_type='application/json', HTTP_X_API_KEY=self.api_key)
        self.assertEqual(resp.status_code, 200)
        res = resp.json()
        token = res['data'].get('payment_token')
        # Now query status
        status_url = reverse('api:api_transaction_status')
        resp2 = self.client.get(status_url + f'?payment_token={token}', HTTP_X_API_KEY=self.api_key)
        self.assertEqual(resp2.status_code, 200)
        sdata = resp2.json()
        self.assertTrue(sdata.get('success'))
        self.assertIn('data', sdata)
        # data content may vary; ensure payment_token present
        self.assertEqual(sdata['data'].get('payment_token'), token)
