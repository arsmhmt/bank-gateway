from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from core.models import DepositRequest, WithdrawalRequest, PaymentTransaction, Client, BankAccount
from branches.models import Branch
from crypto.models import CryptoPayment, CryptoWalletConfig

User = get_user_model()


class Command(BaseCommand):
    help = "Delete all demo data (branches with site_code starting 'DEMO-' and demo teminci)."

    @transaction.atomic
    def handle(self, *args, **options):
        demo_branches = Branch.objects.filter(site_code__startswith="DEMO-")
        demo_branch_ids = list(demo_branches.values_list("id", flat=True))

        self.stdout.write(f"Found {len(demo_branch_ids)} demo branches.")

        # Delete related objects where branch is a demo branch
        if demo_branch_ids:
            DepositRequest.objects.filter(branch_id__in=demo_branch_ids).delete()
            WithdrawalRequest.objects.filter(branch_id__in=demo_branch_ids).delete()
            CryptoPayment.objects.filter(branch_id__in=demo_branch_ids).delete()
            PaymentTransaction.objects.filter(branch_id__in=demo_branch_ids).delete()
            CryptoWalletConfig.objects.filter(branch_id__in=demo_branch_ids).delete()

        # Delete bank accounts belonging to demo provider(s)
        demo_providers = User.objects.filter(username__in=["demo_teminci"])  # extend if needed
        BankAccount.objects.filter(provider__in=demo_providers).delete()

        # Delete demo branches themselves
        demo_branches.delete()

        # Remove demo users and demo clients
        User.objects.filter(username__in=["demo_teminci", "demo_site"]).delete()
        Client.objects.filter(name__icontains="Demo Client").delete()

        self.stdout.write(self.style.SUCCESS("Demo data cleared."))
