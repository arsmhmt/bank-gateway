from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal

from provider_panel.models import Provider
from core.models import (
    DepositRequest,
    WithdrawalRequest,
    ProviderCommission,
    ProviderSettlementPayment,
    BankAccount,
)

User = get_user_model()


class FinancialsTests(TestCase):
    def setUp(self):
        # create admin
        self.admin = User.objects.create_user(username="admin", password="adminpass")
        self.admin.role = User.ROLE_OWNER
        self.admin.save()

        # provider user + profile
        self.provider_user = User.objects.create_user(username="prov", password="provpass", email="prov@example.com")
        self.provider_user.role = User.ROLE_PROVIDER
        self.provider_user.save()

        self.provider = Provider.objects.create(user=self.provider_user, name="Prov 1")

    def test_teslimat_balance_and_settlement_creation(self):
        # create approved deposit and withdrawal
        DepositRequest.objects.create(
            user_name="u1",
            external_user_id="ext1",
            amount=Decimal('1000.00'),
            currency="TRY",
            branch=None,
            provider=self.provider_user,
            status='approved',
            payment_token='t1',
        )
        # create a client for withdrawal (client is required on WithdrawalRequest)
        from core.models import Client
        client = Client.objects.create(name="Client A")
        WithdrawalRequest.objects.create(
            user_name="u1",
            iban="TR000",
            amount=Decimal('200.00'),
            client=client,
            branch=None,
            provider=self.provider_user,
            status='approved',
        )

        # provider commission (earned)
        ProviderCommission.objects.create(
            provider=self.provider,
            transaction_type='deposit',
            transaction_id=1,
            amount=Decimal('50.00'),
        )

        # create settlement of 300
        ProviderSettlementPayment.objects.create(
            provider=self.provider_user,
            amount=Decimal('300.00'),
            created_by=self.admin,
        )

        # login as admin and fetch provider detail
        self.client.force_login(self.admin)
        url = reverse('admin_panel:provider_detail', args=[self.provider.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # expected balance = 1000 - 200 - 50 - 300 = 450
        balance = resp.context.get('teslimat_balance')
        self.assertIsNotNone(balance)
        self.assertEqual(Decimal('450.00'), balance)

    def test_toggle_bank_account_active(self):
        account = BankAccount.objects.create(
            provider=self.provider_user,
            bank_name="Test Bank",
            account_holder="Prov",
            iban="TR000",
            is_active=True,
        )
        self.client.force_login(self.admin)
        url = reverse('admin_panel:toggle_bank_account_active', args=[account.id])
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        account.refresh_from_db()
        self.assertFalse(account.is_active)

    def test_toggle_provider_active(self):
        # initial is True
        self.assertTrue(self.provider_user.is_provider_active_for_deposits)
        self.client.force_login(self.admin)
        url = reverse('admin_panel:toggle_provider_active', args=[self.provider.id])
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.provider_user.refresh_from_db()
        self.assertFalse(self.provider_user.is_provider_active_for_deposits)
