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
    
    def _request(self, method: str, params: Optional[Dict[str, Any]] = None, retry_on_rate_limit: bool = True) -> Dict[str, Any]:
        """
        Выполняет HTTP запрос к TonCenter API.
        
        Args:
            method: Имя метода API (например, 'sendBoc', 'getAddressInformation')
            params: Параметры запроса
            retry_on_rate_limit: Повторять запрос при rate limit (429) с задержкой
            
        Returns:
            dict: Результат запроса из поля 'result'
            
        Raises:
            TonCenterError: Если запрос завершился с ошибкой
            httpx.HTTPError: Если произошла ошибка сети
        """
        import time
        
        if params is None:
            params = {}
        
        # Добавляем API ключ если он есть
        if self.api_key:
            params["api_key"] = self.api_key
        
        url = f"{self.base_url}/{method}"
        max_retries = 3 if retry_on_rate_limit else 0
        retry_delay = 2  # секунды
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"TonCenter request: {method}, params={params} (attempt {attempt + 1}/{max_retries + 1})")
                
                # sendBoc требует POST с JSON body
                # Остальные методы - GET с query params
                if method == "sendBoc":
                    # TonCenter API v2 требует POST с JSON body для sendBoc
                    response = self._client.post(
                        url,
                        json=params,
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    response = self._client.get(url, params=params)
                
                # Проверяем rate limit (429) перед raise_for_status
                if response.status_code == 429 and attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Rate limit exceeded (429) for {method}. "
                        f"Waiting {wait_time}s before retry {attempt + 1}/{max_retries}..."
                    )
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                
                data = response.json()
                
                if not data.get("ok", False):
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"TonCenter API error: {error_msg}")
                    raise TonCenterError(f"TonCenter API error: {error_msg}")
                
                result = data.get("result", {})
                logger.debug(f"TonCenter response: {method} -> success")
                
                return result
                
            except httpx.HTTPStatusError as e:
                # Обрабатываем ошибки HTTP статусов
                if e.response.status_code == 429 and attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Rate limit exceeded (429) for {method}. "
                        f"Waiting {wait_time}s before retry {attempt + 1}/{max_retries}..."
                    )
                    time.sleep(wait_time)
                    continue  # Повторяем попытку
                
                # Для других ошибок получаем детали из ответа
                error_detail = None
                if e.response is not None:
                    try:
                        error_detail = e.response.json()
                        logger.error(f"HTTP error calling TonCenter {method}: {e}")
                        logger.error(f"Response status: {e.response.status_code}")
                        logger.error(f"Response body: {error_detail}")
                    except Exception:
                        # Если не удалось распарсить JSON, пробуем получить текст
                        try:
                            error_text = e.response.text
                            logger.error(f"HTTP error calling TonCenter {method}: {e}")
                            logger.error(f"Response status: {e.response.status_code}")
                            logger.error(f"Response text: {error_text[:500]}")
                        except:
                            pass
                
                error_msg = f"HTTP error: {e}"
                if error_detail:
                    error_msg += f". Details: {error_detail}"
                raise TonCenterError(error_msg) from e
            except httpx.HTTPError as e:
                # Для других HTTP ошибок (не статус коды)
                logger.error(f"HTTP error calling TonCenter {method}: {e}")
                raise TonCenterError(f"HTTP error: {e}") from e
            except Exception as e:
                # Если это не последняя попытка, продолжаем цикл
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Unexpected error for {method}: {e}. "
                        f"Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                    continue
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
    
    def get_transactions(self, address: str, limit: int = 10) -> list:
        """
        Получает последние транзакции адреса.
        
        Args:
            address: Адрес кошелька
            limit: Количество транзакций (по умолчанию 10)
            
        Returns:
            list: Список транзакций
        """
        logger.debug(f"Getting transactions for {address}")
        return self._request("getTransactions", {
            "address": address,
            "limit": limit
        })
    
    def get_wallet_seqno(self, address: str) -> int:
        """
        Получает текущий seqno кошелька.
        
        Args:
            address: Адрес кошелька
            
        Returns:
            int: Текущий seqno кошелька (или 0 если кошелек не инициализирован)
        """
        try:
            # Пробуем получить информацию об адресе для проверки статуса
            addr_info = self.get_address_information(address)
            account_state = addr_info.get("state", "")
            
            # Если адрес uninitialized или не существует, возвращаем 0
            if account_state in ("uninit", ""):
                logger.debug(f"Wallet {address} is uninitialized, using seqno=0")
                return 0
            
            # Пробуем получить seqno через runGetMethod
            try:
                result = self.run_get_method(address, "seqno")
                # Парсим результат get method (обычно это список в формате TonCenter)
                stack = result.get("stack", [])
                if stack and len(stack) > 0:
                    # Первый элемент стека - это seqno
                    seqno_value = stack[0]
                    if isinstance(seqno_value, (list, dict)):
                        # TonCenter возвращает числа в специальном формате
                        # Формат: ["num", "0x..."] или {"type": "num", "value": "0x..."}
                        if isinstance(seqno_value, list) and len(seqno_value) >= 2:
                            # Извлекаем значение (может быть в hex или decimal)
                            seqno_str = str(seqno_value[1])
                            if seqno_str.startswith("0x"):
                                seqno = int(seqno_str, 16)
                            else:
                                seqno = int(seqno_str)
                            logger.debug(f"Got seqno={seqno} for wallet {address}")
                            return seqno
                        elif isinstance(seqno_value, dict):
                            seqno = int(seqno_value.get("value", 0))
                            logger.debug(f"Got seqno={seqno} for wallet {address}")
                            return seqno
                    seqno = int(seqno_value)
                    logger.debug(f"Got seqno={seqno} for wallet {address}")
                    return seqno
            except Exception as get_method_error:
                # Если runGetMethod не работает, пробуем получить seqno из последних транзакций
                logger.debug(f"runGetMethod failed for {address}, trying getTransactions: {get_method_error}")
                try:
                    # Получаем последние транзакции и извлекаем seqno из последней
                    transactions = self._request("getTransactions", {
                        "address": address,
                        "limit": 1
                    })
                    
                    if transactions and len(transactions) > 0:
                        # Последняя транзакция содержит информацию о seqno
                        last_tx = transactions[0]
                        # В транзакции может быть поле in_msg или out_msgs с информацией о seqno
                        # Ищем seqno в структуре транзакции
                        # Обычно seqno находится в in_msg или в данных транзакции
                        if "in_msg" in last_tx and last_tx["in_msg"]:
                            in_msg = last_tx["in_msg"]
                            # Проверяем, есть ли seqno в сообщении
                            if "source" in in_msg and in_msg["source"] == address:
                                # Это исходящее сообщение от нашего кошелька
                                # Seqno может быть в структуре сообщения
                                pass
                        
                        # Альтернативный способ: ищем seqno в out_msgs
                        if "out_msgs" in last_tx and last_tx["out_msgs"]:
                            for out_msg in last_tx["out_msgs"]:
                                # Seqno может быть в структуре исходящего сообщения
                                pass
                        
                        # Если не нашли seqno в транзакции, возвращаем 0
                        logger.warning(f"Could not extract seqno from transactions for {address}")
                        return 0
                    else:
                        logger.warning(f"No transactions found for {address}, using seqno=0")
                        return 0
                except Exception as tx_error:
                    logger.warning(f"Could not get transactions for {address}: {tx_error}")
                    return 0
            
            return 0
        except Exception as e:
            # Если метод не найден (404), кошелек может быть не инициализирован
            # или использовать другой формат - возвращаем 0
            logger.warning(
                f"Could not get seqno for {address}: {e}. "
                f"Using seqno=0. This may cause issues if wallet is active."
            )
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

