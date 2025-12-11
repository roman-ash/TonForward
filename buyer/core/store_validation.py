"""
Утилиты для валидации официальных магазинов.
"""

import re
from urllib.parse import urlparse
from typing import Tuple, Optional
import logging

from django.db.models import Q

logger = logging.getLogger(__name__)


def extract_domain(url: str) -> str:
    """
    Извлекает домен из URL.
    
    Args:
        url: URL страницы товара
        
    Returns:
        str: Домен (например, 'amazon.com', 'wildberries.ru')
        
    Examples:
        >>> extract_domain('https://www.amazon.com/product/123')
        'amazon.com'
        >>> extract_domain('https://wildberries.ru/catalog/123/detail.aspx')
        'wildberries.ru'
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Убираем www.
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Убираем порт если есть
        if ':' in domain:
            domain = domain.split(':')[0]
        
        return domain.lower()
    except Exception as e:
        logger.error(f"Error extracting domain from URL {url}: {e}")
        raise ValueError(f"Invalid URL format: {url}")


def validate_store_domain(domain: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Проверяет домен магазина по whitelist.
    
    Args:
        domain: Домен магазина
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            - (True, 'VERIFIED', None) - магазин разрешен
            - (True, 'PENDING', None) - магазин условно разрешен (на проверке)
            - (False, 'REJECTED', 'reason') - магазин в черном списке или не найден
    """
    from core.models import OfficialStoreDomain
    
    try:
        store_domain_obj = OfficialStoreDomain.objects.get(domain=domain)
        
        if store_domain_obj.status == OfficialStoreDomain.Status.VERIFIED:
            return True, OfficialStoreDomain.Status.VERIFIED, None
        elif store_domain_obj.status == OfficialStoreDomain.Status.PENDING:
            return True, OfficialStoreDomain.Status.PENDING, None
        elif store_domain_obj.status == OfficialStoreDomain.Status.REJECTED:
            return False, OfficialStoreDomain.Status.REJECTED, f"Магазин {domain} в черном списке"
        else:
            return False, None, "Неизвестный статус магазина"
            
    except OfficialStoreDomain.DoesNotExist:
        # Магазин не найден в базе - требует проверки
        return False, None, f"Магазин {domain} не найден в списке разрешенных"


def get_store_status(domain: str) -> str:
    """
    Получает статус магазина.
    
    Args:
        domain: Домен магазина
        
    Returns:
        str: Статус ('VERIFIED', 'PENDING', 'REJECTED' или 'UNKNOWN')
    """
    from core.models import OfficialStoreDomain
    
    try:
        store_domain_obj = OfficialStoreDomain.objects.get(domain=domain)
        return store_domain_obj.status
    except OfficialStoreDomain.DoesNotExist:
        return 'UNKNOWN'

