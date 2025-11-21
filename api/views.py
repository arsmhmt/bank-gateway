
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Site, DepositRequest, WithdrawalRequest, APIRequestLog
from django.utils.timezone import now
from django.views.decorators.http import require_POST
import json

def validate_api_key(request):
    key = request.headers.get('X-API-KEY')
    return Site.objects.filter(api_key=key).first()

@csrf_exempt
@require_POST
def init_deposit(request):
    site = validate_api_key(request)
    if not site:
        return JsonResponse({'status': 'error', 'message': 'API key invalid'}, status=403)
    try:
        data = json.loads(request.body)
        token = uuid.uuid4().hex[:16]
        deposit = DepositRequest.objects.create(
            site=site,
            amount=data['amount'],
            user_name=data['user_name'],
            status='pending',
            token=token,
            callback_url=data.get('callback_url')
        )
        APIRequestLog.objects.create(
            site=site,
            request_type='deposit',
            endpoint='/api/deposit/init/',
            status_code=200,
            ip=request.META.get('REMOTE_ADDR')
        )
        return JsonResponse({
            'status': 'success',
            'redirect_url': f"https://paycrypt.online/deposit-form/?bid={deposit.id}&token={token}"
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@require_POST
def init_withdraw(request):
    site = validate_api_key(request)
    if not site:
        return JsonResponse({'status': 'error', 'message': 'API key invalid'}, status=403)
    try:
        data = json.loads(request.body)
        withdraw = WithdrawalRequest.objects.create(
            site=site,
            amount=data['amount'],
            user_name=data['user_name'],
            iban=data['iban'],
            bank_name=data['bank_name'],
            status='pending',
            callback_url=data.get('callback_url')
        )
        APIRequestLog.objects.create(
            site=site,
            request_type='withdraw',
            endpoint='/api/withdraw/init/',
            status_code=200,
            ip=request.META.get('REMOTE_ADDR')
        )
        return JsonResponse({'status': 'success', 'request_id': withdraw.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
