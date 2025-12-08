"""
HTTP клиент для работы с TonCenter API.

Тонкий слой-обёртка для отправки запросов к TonCenter HTTP API.
"""

import os
from typing import Dict, Any, Optional
import logging

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


class TonCenterError(Exception):
    """Исключение для ошибок TonCenter API."""
    pass


class TonCenterClient:
    """
    HTTP клиент для TonCenter API v2.
    
    Тонкая обёртка над HTTP API для отправки и получения данных из TON blockchain.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Инициализирует клиент TonCenter.
        
        Args:
            api_key: API ключ для TonCenter (опционально, берется из TONCENTER_API_KEY)
            base_url: Базовый URL TonCenter (по умолчанию https://toncenter.com/api/v2)
        """
        if httpx is None:
            raise ImportError(
                "httpx is required for TonCenterClient. "
                "Install it with: pip install httpx"
            )
        
        self.api_key = api_key or os.getenv("TONCENTER_API_KEY")
        self.base_url = base_url or os.getenv(
            "TONCENTER_URL",
            "https://toncenter.com/api/v2"
        )
        
        # Убираем trailing slash если есть
        self.base_url = self.base_url.rstrip('/')
        
        self._client = httpx.Client(timeout=30.0)
        
        logger.info(f"TonCenterClient initialized: base_url={self.base_url}")
    
    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Выполняет HTTP запрос к TonCenter API.
        
        Args:
            method: Имя метода API (например, 'sendBoc', 'getAddressInformation')
            params: Параметры запроса
            
        Returns:
            dict: Результат запроса из поля 'result'
            
        Raises:
            TonCenterError: Если запрос завершился с ошибкой
            httpx.HTTPError: Если произошла ошибка сети
        """
        if params is None:
            params = {}
        
        # Добавляем API ключ если он есть
        if self.api_key:
            params["api_key"] = self.api_key
        
        url = f"{self.base_url}/{method}"
        
        try:
            logger.debug(f"TonCenter request: {method}, params={params}")
            
            response = self._client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("ok", False):
                error_msg = data.get("error", "Unknown error")
                logger.error(f"TonCenter API error: {error_msg}")
                raise TonCenterError(f"TonCenter API error: {error_msg}")
            
            result = data.get("result", {})
            logger.debug(f"TonCenter response: {method} -> success")
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling TonCenter {method}: {e}")
            raise TonCenterError(f"HTTP error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error calling TonCenter {method}: {e}")
            raise TonCenterError(f"Unexpected error: {e}") from e
    
    def send_boc(self, boc_base64: str) -> Dict[str, Any]:
        """
        Отправляет BOC (Bag of Cells) транзакцию в сеть.
        
        Args:
            boc_base64: BOC транзакции в формате base64
            
        Returns:
            dict: Результат отправки (обычно содержит код результата)
            
        Example:
            >>> client = TonCenterClient()
            >>> result = client.send_boc("te6cckEBAQEA...")
        """
        logger.info("Sending BOC to TON network")
        return self._request("sendBoc", {"boc": boc_base64})
    
    def get_address_information(self, address: str) -> Dict[str, Any]:
        """
        Получает информацию об адресе в TON.
        
        Args:
            address: TON адрес (можно в любом формате)
            
        Returns:
            dict: Информация об адресе (balance, state, etc.)
        """
        logger.debug(f"Getting address information: {address}")
        return self._request("getAddressInformation", {"address": address})
    
    def run_get_method(
        self,
        address: str,
        method: str,
        stack: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Выполняет GET-метод смарт-контракта.
        
        Args:
            address: Адрес контракта
            method: Имя метода для вызова
            stack: Стек параметров (опционально)
            
        Returns:
            dict: Результат выполнения метода
        """
        params = {"address": address, "method": method}
        if stack is not None:
            params["stack"] = stack
        
        logger.debug(f"Running get method {method} on {address}")
        return self._request("runGetMethod", params)
    
    def get_wallet_seqno(self, address: str) -> int:
        """
        Получает текущий seqno кошелька.
        
        Args:
            address: Адрес кошелька
            
        Returns:
            int: Текущий seqno кошелька (или 0 если кошелек не инициализирован)
        """
        try:
            result = self.run_get_method(address, "seqno")
            # Парсим результат get method (обычно это список в формате TonCenter)
            stack = result.get("stack", [])
            if stack and len(stack) > 0:
                # Первый элемент стека - это seqno
                seqno_value = stack[0]
                if isinstance(seqno_value, (list, dict)):
                    # TonCenter возвращает числа в специальном формате
                    seqno = seqno_value[1] if isinstance(seqno_value, list) else seqno_value.get("value", 0)
                    return int(seqno)
                return int(seqno_value)
            return 0
        except Exception as e:
            logger.warning(f"Could not get seqno for {address}: {e}, using 0")
            return 0
    
    def close(self):
        """Закрывает HTTP клиент."""
        if hasattr(self, '_client'):
            self._client.close()
    
    def __enter__(self):
        """Поддержка context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Поддержка context manager."""
        self.close()

