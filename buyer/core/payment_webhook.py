"""
Webhook для обработки платежей от платежных провайдеров.
"""

import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.request import Request

from core.models import Payment, Deal, OrderRequest

logger = logging.getLogger(__name__)


def verify_payment_signature(
    payload: bytes,
    signature: str,
    secret_key: str,
    provider: str
) -> bool:
    """
    Проверяет подпись webhook от платежного провайдера.

    Args:
        payload: Тело запроса (bytes)
        signature: Подпись из заголовка
        secret_key: Секретный ключ провайдера
        provider: Имя провайдера ('yookassa', 'tinkoff', etc.)

    Returns:
        bool: True если подпись валидна
    """
    if provider == 'yookassa':
        # YooKassa использует HMAC-SHA256
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    
    elif provider == 'tinkoff':
        # Tinkoff использует свой алгоритм проверки подписи
        # TODO: Реализовать проверку подписи Tinkoff
        return True
    
    else:
        logger.warning(f"Unknown provider {provider}, skipping signature verification")
        return True


@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(APIView):
    """
    Webhook endpoint для обработки уведомлений от платежных провайдеров.
    
    POST /api/webhooks/payment/
    """

    @csrf_exempt
    def post(self, request: Request) -> JsonResponse:
        """
        Обрабатывает webhook от платежного провайдера.
        """
        try:
            # Определяем провайдера из заголовков или тела запроса
            provider = self._detect_provider(request)
            
            if not provider:
                return JsonResponse(
                    {'error': 'Unknown payment provider'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Получаем секретный ключ для провайдера
            secret_key = self._get_provider_secret_key(provider)
            
            # Проверяем подпись
            payload = request.body
            signature = request.META.get('HTTP_X_SIGNATURE') or request.META.get('HTTP_SIGNATURE', '')
            
            if secret_key and not verify_payment_signature(payload, signature, secret_key, provider):
                logger.warning(f"Invalid signature for provider {provider}")
                return JsonResponse(
                    {'error': 'Invalid signature'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Парсим данные
            try:
                webhook_data = json.loads(payload.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse(
                    {'error': 'Invalid JSON'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Логируем webhook
            logger.info(f"Received webhook from {provider}: {webhook_data}")
            
            # Асинхронно обрабатываем webhook через Celery
            from core.tasks import process_payment_webhook
            process_payment_webhook.delay(provider, webhook_data)
            
            # Сразу возвращаем 200 OK провайдеру
            return JsonResponse({'status': 'ok'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing payment webhook: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _detect_provider(self, request: Request) -> Optional[str]:
        """Определяет провайдера из запроса."""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'yookassa' in user_agent or 'yoomoney' in user_agent:
            return 'yookassa'
        elif 'tinkoff' in user_agent:
            return 'tinkoff'
        elif request.data.get('provider'):
            return request.data.get('provider')
        
        return 'mock'  # Для тестирования
    
    def _get_provider_secret_key(self, provider: str) -> Optional[str]:
        """Получает секретный ключ провайдера из настроек."""
        import os
        
        key_map = {
            'yookassa': os.environ.get('YOOKASSA_SECRET_KEY'),
            'tinkoff': os.environ.get('TINKOFF_SECRET_KEY'),
        }
        
        return key_map.get(provider)


def process_yookassa_webhook(webhook_data: Dict[str, Any]) -> None:
    """
    Обрабатывает webhook от YooKassa.

    Args:
        webhook_data: Данные webhook
    """
    event = webhook_data.get('event')
    payment_id = webhook_data.get('object', {}).get('id')
    
    if event == 'payment.succeeded':
        # Платеж успешен
        try:
            payment = Payment.objects.get(provider_payment_id=payment_id, provider='yookassa')
            payment.status = Payment.Status.SUCCESS
            payment.save()
            
            # Обновляем статусы после успешного платежа
            deal = payment.deal
            order = deal.order
            
            # Обновляем статус заявки на PAID (платеж успешно подтвержден)
            order.status = OrderRequest.Status.PAID
            order.save()
            
            # Статус Deal пока остается NEW, после деплоя контракта станет FUNDED
            
            logger.info(f"Payment {payment.id} marked as SUCCESS, order {order.id} marked as PAID")
            
            # Инициируем деплой on-chain контракта
            # После успешного деплоя статус сделки станет FUNDED
            from core.tasks import deploy_onchain_deal
            deploy_onchain_deal.delay(payment.deal.id)
            
        except Payment.DoesNotExist:
            logger.error(f"Payment with provider_payment_id={payment_id} not found")
    
    elif event == 'payment.canceled':
        # Платеж отменен
        try:
            payment = Payment.objects.get(provider_payment_id=payment_id, provider='yookassa')
            payment.status = Payment.Status.FAILED
            payment.save()
            logger.info(f"Payment {payment.id} marked as FAILED")
        except Payment.DoesNotExist:
            logger.error(f"Payment with provider_payment_id={payment_id} not found")


def process_tinkoff_webhook(webhook_data: Dict[str, Any]) -> None:
    """
    Обрабатывает webhook от Tinkoff.

    Args:
        webhook_data: Данные webhook
    """
    # TODO: Реализовать обработку Tinkoff webhook
    logger.warning("Tinkoff webhook processing not implemented yet")


def process_mock_webhook(webhook_data: Dict[str, Any]) -> None:
    """
    Обрабатывает тестовый webhook (mock).

    Args:
        webhook_data: Данные webhook
    """
    payment_id = webhook_data.get('payment_id')
    status_value = webhook_data.get('status', 'success')
    
    try:
        payment = Payment.objects.get(id=payment_id, provider='mock')
        
        status_mapping = {
            'success': Payment.Status.SUCCESS,
            'failed': Payment.Status.FAILED,
            'pending': Payment.Status.PENDING,
        }
        
        payment.status = status_mapping.get(status_value, Payment.Status.PENDING)
        payment.save()
        
        if payment.status == Payment.Status.SUCCESS:
            deal = payment.deal
            order = deal.order
            
            # Обновляем статус заявки на PAID (платеж успешно подтвержден)
            order.status = OrderRequest.Status.PAID
            order.save()
            
            # Статус Deal пока остается NEW, после деплоя контракта станет FUNDED
            
            logger.info(f"Mock payment {payment.id} marked as SUCCESS, order {order.id} marked as PAID")
            
            # Инициируем деплой on-chain контракта
            # После успешного деплоя статус сделки станет FUNDED
            from core.tasks import deploy_onchain_deal
            deploy_onchain_deal.delay(payment.deal.id)
            
    except Payment.DoesNotExist:
        logger.error(f"Payment with id={payment_id} not found")

