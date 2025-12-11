"""
Фильтр для удаления контактных данных из текстовых полей.
Запрещает передачу телефонов, email, @username, URL.
"""

import re
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


# Паттерны для поиска контактных данных
PHONE_PATTERNS = [
    r'\+?[7-8]?\s?\(?\d{3}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}',  # +7 (999) 123-45-67
    r'\+?[1-9]\d{1,3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{2,4}',  # Международные форматы
    r'\d{3}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}',  # 123-456-78-90
]

EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

TELEGRAM_PATTERN = r'@[A-Za-z0-9_]{5,32}'

URL_PATTERNS = [
    r'https?://[^\s]+',
    r'www\.[^\s]+',
    r't\.me/[^\s]+',
    r'telegram\.me/[^\s]+',
]

SOCIAL_MEDIA_PATTERNS = [
    r'instagram\.com/[^\s]+',
    r'vk\.com/[^\s]+',
    r'facebook\.com/[^\s]+',
    r'twitter\.com/[^\s]+',
]


def contains_contacts(text: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Проверяет, содержит ли текст контактные данные.
    
    Args:
        text: Текст для проверки
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            - (True, 'PHONE', matched_text) - найден телефон
            - (True, 'EMAIL', matched_text) - найден email
            - (True, 'TELEGRAM', matched_text) - найден Telegram username
            - (True, 'URL', matched_text) - найден URL
            - (False, None, None) - контактов не найдено
    """
    if not text:
        return False, None, None
    
    # Проверка телефонов
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            return True, 'PHONE', matches[0]
    
    # Проверка email
    email_matches = re.findall(EMAIL_PATTERN, text)
    if email_matches:
        return True, 'EMAIL', email_matches[0]
    
    # Проверка Telegram
    tg_matches = re.findall(TELEGRAM_PATTERN, text)
    if tg_matches:
        return True, 'TELEGRAM', tg_matches[0]
    
    # Проверка URL
    for pattern in URL_PATTERNS:
        url_matches = re.findall(pattern, text, re.IGNORECASE)
        if url_matches:
            return True, 'URL', url_matches[0]
    
    # Проверка соцсетей
    for pattern in SOCIAL_MEDIA_PATTERNS:
        social_matches = re.findall(pattern, text, re.IGNORECASE)
        if social_matches:
            return True, 'URL', social_matches[0]
    
    return False, None, None


def filter_contacts(text: str, replace_with: str = "[КОНТАКТЫ УДАЛЕНЫ]") -> str:
    """
    Удаляет контактные данные из текста, заменяя их на placeholder.
    
    Args:
        text: Текст для фильтрации
        replace_with: Текст для замены найденных контактов
        
    Returns:
        str: Отфильтрованный текст
    """
    if not text:
        return text
    
    filtered_text = text
    
    # Удаляем телефоны
    for pattern in PHONE_PATTERNS:
        filtered_text = re.sub(pattern, replace_with, filtered_text)
    
    # Удаляем email
    filtered_text = re.sub(EMAIL_PATTERN, replace_with, filtered_text, flags=re.IGNORECASE)
    
    # Удаляем Telegram
    filtered_text = re.sub(TELEGRAM_PATTERN, replace_with, filtered_text)
    
    # Удаляем URL
    for pattern in URL_PATTERNS:
        filtered_text = re.sub(pattern, replace_with, filtered_text, flags=re.IGNORECASE)
    
    # Удаляем соцсети
    for pattern in SOCIAL_MEDIA_PATTERNS:
        filtered_text = re.sub(pattern, replace_with, filtered_text, flags=re.IGNORECASE)
    
    return filtered_text


def validate_text_no_contacts(text: str) -> None:
    """
    Проверяет текст на наличие контактов и выбрасывает исключение если найдены.
    
    Args:
        text: Текст для проверки
        
    Raises:
        ValidationError: Если в тексте найдены контактные данные
    """
    from rest_framework.exceptions import ValidationError
    
    has_contacts, contact_type, matched = contains_contacts(text)
    
    if has_contacts:
        contact_names = {
            'PHONE': 'телефон',
            'EMAIL': 'email',
            'TELEGRAM': 'Telegram username',
            'URL': 'ссылку',
        }
        contact_name = contact_names.get(contact_type, 'контактные данные')
        
        raise ValidationError(
            f"Передача {contact_name} запрещена правилами сервиса. "
            f"Обнаружено: {matched}"
        )

