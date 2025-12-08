"""
API Views for core models.
"""

from decimal import Decimal
from typing import Any

from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request

from core.models import (
    BuyerProfile,
    OrderRequest,
    Deal,
    Payment,
    Shipment,
    Dispute,
    Rating,
)
from core.serializers import (
    BuyerProfileSerializer,
    BuyerProfileCreateSerializer,
    OrderRequestCreateSerializer,
    OrderRequestSerializer,
    OrderBidSerializer,
    DealSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
    ShipmentSerializer,
    DisputeSerializer,
    DisputeCreateSerializer,
    RatingSerializer,
    RatingCreateSerializer,
)


class BuyerProfileViewSet(viewsets.ModelViewSet):
    """ViewSet для профилей байеров."""

    queryset = BuyerProfile.objects.all()
    serializer_class = BuyerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Возвращает соответствующий сериализатор."""
        if self.action == 'create':
            return BuyerProfileCreateSerializer
        return BuyerProfileSerializer

    def get_queryset(self):
        """Фильтрует queryset по текущему пользователю."""
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer: BuyerProfileCreateSerializer) -> None:
        """Создает профиль байера для текущего пользователя."""
        serializer.save(user=self.request.user)


class OrderRequestViewSet(viewsets.ModelViewSet):
    """ViewSet для заявок заказчиков."""

    queryset = OrderRequest.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Возвращает соответствующий сериализатор."""
        if self.action == 'create':
            return OrderRequestCreateSerializer
        return OrderRequestSerializer

    def get_queryset(self):
        """Фильтрует queryset."""
        user = self.request.user
        queryset = self.queryset

        # Заказчики видят только свои заявки
        if user.user_type == 'client':
            queryset = queryset.filter(customer=user)
        # Байеры видят все открытые заявки
        elif user.user_type == 'worker':
            queryset = queryset.filter(status=OrderRequest.Status.OPEN)
        # Админы видят все
        elif user.is_staff:
            pass

        return queryset

    @action(detail=True, methods=['post'], url_path='bids')
    def create_bid(self, request: Request, pk: int = None) -> Response:
        """
        Отклик байера на заявку.
        POST /api/orders/{order_id}/bids/
        """
        order = self.get_object()
        
        serializer = OrderBidSerializer(
            data=request.data,
            context={'request': request, 'order': order}
        )
        serializer.is_valid(raise_exception=True)

        # Получаем профиль байера
        buyer_profile = request.user.buyer_profile

        # Создаем сделку (пока без конвертации в TON - это будет в другом месте)
        # Здесь просто создаем Deal для дальнейшей обработки
        # В реальности здесь должна быть логика выбора байера заказчиком,
        # но для упрощения сразу создаем Deal

        # TODO: В будущем здесь должен быть механизм выбора байера заказчиком
        # Пока создаем Deal напрямую
        
        # Конвертируем рубли в TON (заглушка - нужен сервис получения курса)
        rate_rub_ton = Decimal('250.0')  # TODO: получить реальный курс
        
        with transaction.atomic():
            deal = Deal.objects.create(
                order=order,
                customer=order.customer,
                buyer=buyer_profile,
                item_price_max_rub=order.max_item_price_rub,
                buyer_fee_rub=order.buyer_fee_rub,
                service_fee_rub=order.service_fee_rub,
                insurance_rub=order.insurance_rub,
                item_price_ton=order.max_item_price_rub / rate_rub_ton,
                buyer_fee_ton=order.buyer_fee_rub / rate_rub_ton,
                service_fee_ton=order.service_fee_rub / rate_rub_ton,
                insurance_ton=order.insurance_rub / rate_rub_ton,
                purchase_deadline=timezone.now() + timedelta(days=1),
                ship_deadline=timezone.now() + timedelta(days=3),
                confirm_deadline=timezone.now() + timedelta(days=14),
                status=Deal.Status.NEW,
            )

            # Обновляем статус заявки
            order.status = OrderRequest.Status.MATCHED
            order.save()

        return Response({
            'message': 'Отклик принят. Сделка создана.',
            'deal_id': deal.id
        }, status=status.HTTP_201_CREATED)


class DealViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для сделок."""

    queryset = Deal.objects.all()
    serializer_class = DealSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Фильтрует queryset по текущему пользователю."""
        user = self.request.user
        queryset = self.queryset

        if user.is_staff:
            return queryset

        # Пользователь видит сделки, где он заказчик или байер
        queryset = queryset.filter(
            customer=user
        ) | queryset.filter(
            buyer__user=user
        )

        return queryset.distinct()

    @action(detail=True, methods=['post'], url_path='mark-purchased')
    def mark_purchased(self, request: Request, pk: int = None) -> Response:
        """
        Байер отмечает, что товар куплен.
        POST /api/deals/{deal_id}/mark-purchased/
        """
        from rest_framework.exceptions import PermissionDenied, ValidationError
        
        deal = self.get_object()
        
        # Проверяем, что это байер этой сделки
        if deal.buyer.user != request.user:
            raise PermissionDenied("Только байер может отметить товар как купленный.")
        
        # Проверяем статус сделки
        if deal.status != Deal.Status.FUNDED:
            raise ValidationError(
                f"Товар можно отметить как купленный только для сделки со статусом FUNDED. "
                f"Текущий статус: {deal.status}"
            )
        
        # Обновляем статус
        deal.status = Deal.Status.PURCHASED
        deal.save()
        
        # Вызываем on-chain метод mark_purchased
        if hasattr(deal, 'onchain_deal'):
            from core.ton_utils import call_contract_method, sync_deal_status_from_chain
            try:
                result = call_contract_method(
                    deal.onchain_deal.contract_address,
                    'mark_purchased',
                    {}
                )
                logger.info(f"Contract method mark_purchased result: {result}")
                
                # Синхронизируем статус с блокчейна
                sync_deal_status_from_chain(deal.onchain_deal)
            except Exception as e:
                logger.error(f"Error calling mark_purchased: {e}", exc_info=True)
        
        return Response({
            'deal_id': deal.id,
            'status': deal.status,
            'message': 'Товар отмечен как купленный'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='confirm-delivery')
    def confirm_delivery(self, request: Request, pk: int = None) -> Response:
        """
        Заказчик подтверждает получение товара.
        POST /api/deals/{deal_id}/confirm-delivery/
        """
        from rest_framework.exceptions import PermissionDenied, ValidationError
        
        deal = self.get_object()
        
        # Проверяем, что это заказчик этой сделки
        if deal.customer != request.user:
            raise PermissionDenied("Только заказчик может подтвердить получение товара.")
        
        # Проверяем статус сделки
        if deal.status != Deal.Status.SHIPPED:
            raise ValidationError(
                f"Получение можно подтвердить только для сделки со статусом SHIPPED. "
                f"Текущий статус: {deal.status}"
            )
        
        # Обновляем статус
        deal.status = Deal.Status.COMPLETED
        deal.save()
        
        # TODO: Вызвать on-chain метод confirm_delivery через Celery
        if hasattr(deal, 'onchain_deal'):
            from core.ton_utils import call_contract_method
            try:
                result = call_contract_method(
                    deal.onchain_deal.contract_address,
                    'confirm_delivery',
                    {}
                )
                logger.info(f"Contract method confirm_delivery result: {result}")
                
                # Синхронизируем статус
                from core.ton_utils import sync_deal_status_from_chain
                sync_deal_status_from_chain(deal.onchain_deal)
            except Exception as e:
                logger.error(f"Error calling confirm_delivery: {e}", exc_info=True)
        
        return Response({
            'deal_id': deal.id,
            'status': deal.status,
            'message': 'Получение товара подтверждено'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='pay')
    def create_payment(self, request: Request, pk: int = None) -> Response:
        """
        Создание платежа для сделки.
        POST /api/deals/{deal_id}/pay/
        """
        deal = self.get_object()

        serializer = PaymentCreateSerializer(
            data={},
            context={'request': request, 'deal': deal}
        )
        serializer.is_valid(raise_exception=True)

        # Вычисляем общую сумму через метод модели
        total_amount = deal.get_total_amount_rub()

        # Создаем платеж
        payment = Payment.objects.create(
            deal=deal,
            provider='mock',  # TODO: использовать реальный провайдер
            amount_rub=total_amount,
            status=Payment.Status.PENDING,
        )

        # TODO: Инициировать реальный платёж у провайдера
        # Пока заглушка
        payment_url = f'/payment/{payment.id}/'  # TODO: реальный URL платежа

        # НЕ обновляем статус заявки на PAID здесь - это будет сделано в webhook
        # после подтверждения успешного платежа от провайдера

        return Response({
            'payment_id': payment.id,
            'amount_rub': str(total_amount),
            'payment_url': payment_url,
            'status': payment.status,
            'message': 'Платеж создан. После успешной оплаты статус будет обновлен через webhook.'
        }, status=status.HTTP_201_CREATED)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для платежей."""

    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Фильтрует queryset по текущему пользователю."""
        user = self.request.user
        queryset = self.queryset

        if user.is_staff:
            return queryset

        # Пользователь видит платежи своих сделок
        queryset = queryset.filter(
            deal__customer=user
        ) | queryset.filter(
            deal__buyer__user=user
        )

        return queryset.distinct()


class ShipmentViewSet(viewsets.ModelViewSet):
    """ViewSet для отправок."""

    queryset = Shipment.objects.all()
    serializer_class = ShipmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Фильтрует queryset по текущему пользователю."""
        user = self.request.user
        queryset = self.queryset

        if user.is_staff:
            return queryset

        # Пользователь видит отправки своих сделок
        queryset = queryset.filter(
            deal__customer=user
        ) | queryset.filter(
            deal__buyer__user=user
        )

        return queryset.distinct()

    def perform_create(self, serializer: ShipmentSerializer) -> None:
        """Создает отправку и обновляет статус сделки."""
        from rest_framework.exceptions import PermissionDenied, ValidationError
        
        # Получаем deal из validated_data (после is_valid, но ДО сохранения в БД)
        # deal должен быть передан в запросе, если его нет в read_only_fields
        # Если deal в read_only_fields, получаем его из request.data
        if 'deal' in serializer.validated_data:
            deal = serializer.validated_data['deal']
        else:
            # Если deal в read_only, получаем из request.data
            deal_id = self.request.data.get('deal')
            if not deal_id:
                raise ValidationError("deal is required")
            try:
                deal = Deal.objects.get(pk=deal_id)
            except Deal.DoesNotExist:
                raise ValidationError(f"Deal with id {deal_id} not found")
        
        user = self.request.user
        
        # Проверки ДО сохранения в БД
        # Проверяем, что только байер может создать отправку
        if deal.buyer.user != user:
            raise PermissionDenied("Только байер может создать отправку.")
        
        # Проверяем статус сделки - отправка возможна только после покупки
        if deal.status != Deal.Status.PURCHASED:
            raise ValidationError(
                f"Нельзя отправлять товар до статуса PURCHASED. Текущий статус: {deal.status}"
            )
        
        # Сохраняем shipment только после всех проверок
        shipment = serializer.save()
        
        # Обновляем статус сделки на SHIPPED (НЕ COMPLETED!)
        deal.status = Deal.Status.SHIPPED
        deal.save()
        
        # Вызываем on-chain метод mark_shipped
        if hasattr(deal, 'onchain_deal'):
            from core.ton_utils import call_contract_method, sync_deal_status_from_chain
            try:
                result = call_contract_method(
                    deal.onchain_deal.contract_address,
                    'mark_shipped',
                    {}
                )
                logger.info(f"Contract method mark_shipped result: {result}")
                
                # Синхронизируем статус с блокчейна
                sync_deal_status_from_chain(deal.onchain_deal)
            except Exception as e:
                logger.error(f"Error calling mark_shipped: {e}", exc_info=True)


class DisputeViewSet(viewsets.ModelViewSet):
    """ViewSet для споров."""

    queryset = Dispute.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Возвращает соответствующий сериализатор."""
        if self.action == 'create':
            return DisputeCreateSerializer
        return DisputeSerializer

    def get_queryset(self):
        """Фильтрует queryset по текущему пользователю."""
        user = self.request.user
        queryset = self.queryset

        if user.is_staff:
            return queryset

        # Пользователь видит споры своих сделок
        queryset = queryset.filter(
            deal__customer=user
        ) | queryset.filter(
            deal__buyer__user=user
        )

        return queryset.distinct()

    @action(detail=False, methods=['post'], url_path='deal/(?P<deal_id>[^/.]+)')
    def create_for_deal(self, request: Request, deal_id: int = None) -> Response:
        """Создание спора для конкретной сделки."""
        try:
            deal = Deal.objects.get(pk=deal_id)
        except Deal.DoesNotExist:
            return Response(
                {'error': 'Сделка не найдена.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = DisputeCreateSerializer(
            data=request.data,
            context={'request': request, 'deal': deal}
        )
        serializer.is_valid(raise_exception=True)
        
        dispute = serializer.save()
        
        # Обновляем статус сделки
        deal.status = Deal.Status.DISPUTE
        deal.save()

        return Response(
            DisputeSerializer(dispute).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request: Request, pk: int = None) -> Response:
        """
        Разрешение спора арбитром.
        POST /api/disputes/{dispute_id}/resolve/
        
        Body:
        {
            "resolution": "REFUND_CUSTOMER" | "PAY_BUYER" | "SPLIT"
        }
        """
        from rest_framework.exceptions import PermissionDenied, ValidationError
        
        dispute = self.get_object()
        
        # Проверяем, что это staff (арбитр)
        if not request.user.is_staff:
            raise PermissionDenied("Только арбитр (staff) может разрешить спор.")
        
        # Проверяем, что спор еще не разрешен
        if dispute.resolution != Dispute.Resolution.PENDING:
            raise ValidationError(f"Спор уже разрешен: {dispute.resolution}")
        
        resolution = request.data.get('resolution')
        valid_resolutions = [r[0] for r in Dispute.Resolution.choices if r[0] != 'PENDING']
        if resolution not in valid_resolutions:
            raise ValidationError(f"Недопустимое разрешение: {resolution}. Допустимые: {', '.join(valid_resolutions)}")
        
        # Обновляем спор
        dispute.resolution = resolution
        dispute.resolved_by = request.user
        dispute.resolved_at = timezone.now()
        dispute.save()
        
        # Обновляем статус сделки в зависимости от разрешения
        deal = dispute.deal
        if resolution == Dispute.Resolution.REFUND_CUSTOMER:
            deal.status = Deal.Status.CANCELLED_REFUND_CUSTOMER
        elif resolution == Dispute.Resolution.PAY_BUYER:
            deal.status = Deal.Status.CANCELLED_PAY_BUYER
        elif resolution == Dispute.Resolution.SPLIT:
            # TODO: Реализовать логику разделения средств
            deal.status = Deal.Status.COMPLETED
        deal.save()
        
        # Вызываем on-chain метод resolve_dispute
        if hasattr(deal, 'onchain_deal'):
            from core.ton_utils import call_contract_method, sync_deal_status_from_chain
            try:
                method_name = f'resolve_dispute_{resolution.lower()}'
                result = call_contract_method(
                    deal.onchain_deal.contract_address,
                    method_name,
                    {}
                )
                logger.info(f"Contract method {method_name} result: {result}")
                
                # Синхронизируем статус
                sync_deal_status_from_chain(deal.onchain_deal)
            except Exception as e:
                logger.error(f"Error calling {method_name}: {e}", exc_info=True)
        
        return Response(
            DisputeSerializer(dispute).data,
            status=status.HTTP_200_OK
        )


class RatingViewSet(viewsets.ModelViewSet):
    """ViewSet для рейтингов."""

    queryset = Rating.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Возвращает соответствующий сериализатор."""
        if self.action == 'create':
            return RatingCreateSerializer
        return RatingSerializer

    def get_queryset(self):
        """Фильтрует queryset."""
        user = self.request.user
        queryset = self.queryset

        if user.is_staff:
            return queryset

        # Пользователь видит рейтинги, где он участвовал
        queryset = queryset.filter(
            deal__customer=user
        ) | queryset.filter(
            deal__buyer__user=user
        ) | queryset.filter(
            rated_by=user
        ) | queryset.filter(
            rated_user=user
        )

        return queryset.distinct()

    @action(detail=False, methods=['post'], url_path='deal/(?P<deal_id>[^/.]+)')
    def create_for_deal(self, request: Request, deal_id: int = None) -> Response:
        """Создание рейтинга для конкретной сделки."""
        try:
            deal = Deal.objects.get(pk=deal_id)
        except Deal.DoesNotExist:
            return Response(
                {'error': 'Сделка не найдена.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RatingCreateSerializer(
            data=request.data,
            context={'request': request, 'deal': deal}
        )
        serializer.is_valid(raise_exception=True)
        
        rating = serializer.save()
        
        # Обновляем рейтинг байера (если оценивали байера)
        if hasattr(rating.rated_user, 'buyer_profile'):
            buyer_profile = rating.rated_user.buyer_profile
            # Вычисляем средний рейтинг
            ratings = Rating.objects.filter(rated_user=rating.rated_user)
            if ratings.count() > 0:
                avg_rating = sum(r.score for r in ratings) / ratings.count()
                buyer_profile.rating = avg_rating
                buyer_profile.deals_completed = ratings.count()
                buyer_profile.save()

        return Response(
            RatingSerializer(rating).data,
            status=status.HTTP_201_CREATED
        )
