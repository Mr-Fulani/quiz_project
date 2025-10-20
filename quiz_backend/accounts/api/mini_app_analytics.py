"""
API endpoints для аналитики мини-приложения.
Доступны только для администраторов.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
import logging

from accounts.models import MiniAppUser, TelegramAdmin, DjangoAdmin
from donation.models import Donation

logger = logging.getLogger(__name__)


def check_admin_access(telegram_id):
    """
    Проверяет, является ли пользователь администратором.
    
    Args:
        telegram_id: Telegram ID пользователя
        
    Returns:
        bool: True если пользователь является админом, иначе False
    """
    try:
        # Проверяем, есть ли пользователь в MiniAppUser
        mini_app_user = MiniAppUser.objects.filter(telegram_id=telegram_id).first()
        
        if not mini_app_user:
            return False
        
        # Проверяем связи с админами
        # 1. Проверяем связь с Django админом (суперпользователь)
        if mini_app_user.django_admin and mini_app_user.django_admin.is_superuser:
            logger.info(f"✅ User {telegram_id} is Django superuser")
            return True
        
        # 2. Проверяем связь с Telegram админом
        if mini_app_user.telegram_admin and mini_app_user.telegram_admin.is_active:
            logger.info(f"✅ User {telegram_id} is Telegram admin")
            return True
        
        logger.warning(f"⚠️ User {telegram_id} is not an admin")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error checking admin access for {telegram_id}: {e}")
        return False


@api_view(['GET'])
@permission_classes([AllowAny])
def donations_analytics(request):
    """
    Статистика по донатам.
    
    Query params:
        - telegram_id: ID пользователя для проверки прав доступа
        
    Returns:
        - total_donations: общее количество донатов
        - total_amount_usd: общая сумма в USD
        - monthly_donations: количество донатов за последний месяц
        - monthly_amount_usd: сумма за месяц в USD
        - by_source: разбивка по источникам (website/mini_app)
    """
    telegram_id = request.GET.get('telegram_id')
    
    if not telegram_id:
        return Response(
            {'error': 'telegram_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Проверка прав доступа
    if not check_admin_access(int(telegram_id)):
        return Response(
            {'error': 'Access denied. Admin privileges required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Общая статистика
        completed_donations = Donation.objects.filter(status='completed')
        total_donations = completed_donations.count()
        total_amount_usd = completed_donations.filter(
            currency='usd'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Статистика за последний месяц
        one_month_ago = timezone.now() - timedelta(days=30)
        monthly_donations_qs = completed_donations.filter(created_at__gte=one_month_ago)
        monthly_donations = monthly_donations_qs.count()
        monthly_amount_usd = monthly_donations_qs.filter(
            currency='usd'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Разбивка по источникам
        by_source = {}
        for source_code, source_name in Donation.SOURCE_CHOICES:
            source_donations = completed_donations.filter(source=source_code)
            by_source[source_code] = {
                'name': str(source_name),
                'count': source_donations.count(),
                'amount_usd': source_donations.filter(
                    currency='usd'
                ).aggregate(total=Sum('amount'))['total'] or 0
            }
        
        return Response({
            'success': True,
            'total_donations': total_donations,
            'total_amount_usd': float(total_amount_usd),
            'monthly_donations': monthly_donations,
            'monthly_amount_usd': float(monthly_amount_usd),
            'by_source': by_source
        })
        
    except Exception as e:
        logger.error(f"Error in donations_analytics: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def subscriptions_analytics(request):
    """
    Статистика по подписчикам мини-аппа.
    
    Query params:
        - telegram_id: ID пользователя для проверки прав доступа
        
    Returns:
        - total_users: общее количество пользователей
        - monthly_new_users: новые пользователи за месяц
        - weekly_new_users: новые пользователи за неделю
    """
    telegram_id = request.GET.get('telegram_id')
    
    if not telegram_id:
        return Response(
            {'error': 'telegram_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Проверка прав доступа
    if not check_admin_access(int(telegram_id)):
        return Response(
            {'error': 'Access denied. Admin privileges required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Общее количество пользователей
        total_users = MiniAppUser.objects.count()
        
        # Новые пользователи за месяц
        one_month_ago = timezone.now() - timedelta(days=30)
        monthly_new_users = MiniAppUser.objects.filter(
            created_at__gte=one_month_ago
        ).count()
        
        # Новые пользователи за неделю
        one_week_ago = timezone.now() - timedelta(days=7)
        weekly_new_users = MiniAppUser.objects.filter(
            created_at__gte=one_week_ago
        ).count()
        
        return Response({
            'success': True,
            'total_users': total_users,
            'monthly_new_users': monthly_new_users,
            'weekly_new_users': weekly_new_users
        })
        
    except Exception as e:
        logger.error(f"Error in subscriptions_analytics: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_analytics(request):
    """
    Статистика по активности пользователей.
    
    Query params:
        - telegram_id: ID пользователя для проверки прав доступа
        
    Returns:
        - active_7_days: активные за последние 7 дней
        - active_30_days: активные за последние 30 дней
        - online_now: онлайн сейчас (активность в последние 5 минут)
    """
    telegram_id = request.GET.get('telegram_id')
    
    if not telegram_id:
        return Response(
            {'error': 'telegram_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Проверка прав доступа
    if not check_admin_access(int(telegram_id)):
        return Response(
            {'error': 'Access denied. Admin privileges required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Активные за 7 дней
        seven_days_ago = timezone.now() - timedelta(days=7)
        active_7_days = MiniAppUser.objects.filter(
            last_seen__gte=seven_days_ago
        ).count()
        
        # Активные за 30 дней
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_30_days = MiniAppUser.objects.filter(
            last_seen__gte=thirty_days_ago
        ).count()
        
        # Онлайн сейчас (активность в последние 5 минут)
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        online_now = MiniAppUser.objects.filter(
            last_seen__gte=five_minutes_ago
        ).count()
        
        return Response({
            'success': True,
            'active_7_days': active_7_days,
            'active_30_days': active_30_days,
            'online_now': online_now
        })
        
    except Exception as e:
        logger.error(f"Error in activity_analytics: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def overview_analytics(request):
    """
    Общая статистика - dashboard с ключевыми метриками.
    
    Query params:
        - telegram_id: ID пользователя для проверки прав доступа
        
    Returns:
        Объединенные данные из всех аналитических endpoints
    """
    telegram_id = request.GET.get('telegram_id')
    
    if not telegram_id:
        return Response(
            {'error': 'telegram_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Проверка прав доступа
    if not check_admin_access(int(telegram_id)):
        return Response(
            {'error': 'Access denied. Admin privileges required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Получаем данные из всех методов
        donations_data = donations_analytics(request).data
        subscriptions_data = subscriptions_analytics(request).data
        activity_data = activity_analytics(request).data
        
        return Response({
            'success': True,
            'donations': donations_data,
            'subscriptions': subscriptions_data,
            'activity': activity_data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in overview_analytics: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

