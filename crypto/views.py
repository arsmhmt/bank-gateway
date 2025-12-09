from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from crypto.models import CryptoPayment
from crypto.services import mark_crypto_confirmed, fail_crypto_payment
from django.conf import settings


def _validate_secret(request):
    provided = request.headers.get("X-Crypto-Secret") or request.GET.get("secret")
    expected = getattr(settings, "CRYPTO_WEBHOOK_SECRET", "")
    return expected and provided == expected


@csrf_exempt
def crypto_webhook(request):
    if not _validate_secret(request):
        return HttpResponseBadRequest("Invalid secret")

    payment_id = request.POST.get("payment_id") or request.GET.get("payment_id")
    tx_hash = request.POST.get("tx_hash") or request.GET.get("tx_hash")
    status = (request.POST.get("status") or request.GET.get("status") or "confirmed").lower()

    if not payment_id:
        return HttpResponseBadRequest("payment_id missing")

    payment = get_object_or_404(CryptoPayment, id=payment_id)

    if status == "confirmed" and tx_hash:
        mark_crypto_confirmed(payment, tx_hash)
        result = {"success": True, "payment": payment.id, "status": payment.status}
    elif status == "failed":
        fail_crypto_payment(payment, reason="Webhook failure")
        result = {"success": False, "payment": payment.id, "status": payment.status}
    else:
        return HttpResponseBadRequest("Invalid payload")

    return JsonResponse(result)
