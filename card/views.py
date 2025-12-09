from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from card.models import CardPayment
from card.services import finalize_psp_checkout


def psp_pending(request, payment_id):
    card_payment = get_object_or_404(CardPayment, id=payment_id)
    context = {
        "card_payment": card_payment,
        "psp_redirect_url": card_payment.psp_redirect_url,
    }
    return render(request, "card/psp_pending.html", context)


@csrf_exempt
def psp_callback(request, payment_id):
    card_payment = get_object_or_404(CardPayment, id=payment_id)
    status = (
        request.POST.get("status")
        or request.GET.get("status")
        or "success"
    ).lower()

    if status not in {"success", "failed"}:
        return HttpResponseBadRequest("Invalid status")

    finalize_psp_checkout(card_payment, success=(status == "success"))

    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"success": status == "success"})

    return redirect("public_card_deposit", code=card_payment.branch.public_code)
