# -*- coding: utf-8 -*-

import asyncio
import logging
import math
from ipaddress import IPv4Network, IPv4Address, ip_address as parse_ip_address

from django.core.management.base import BaseCommand
from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, nextCmd
)
# Убедитесь, что путь импорта модели Switch корректен для вашей структуры проекта
from snmp.models import Switch

# Настройка базового логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Получение логгера для этого модуля
logger = logging.getLogger(__name__)


def mw_to_dbm(value_str):
    """
    Конвертирует значение мощности из предполагаемых микроватт (uW) в dBm.
    Принимает строку, пытается конвертировать в float.
    Возвращает float (dBm) или None при ошибке или некорректном вводе.
    """
    if value_str is None:
        # logger.debug("mw_to_dbm: Received None input.")
        return None
    try:
        # Пытаемся преобразовать строку в число
        power_uw = float(value_str)
        # logger.debug(f"mw_to_dbm: Input string='{value_str}', float value (uW)={power_uw}")

        if power_uw > 0:
            # Конвертируем микроватты (uW) в милливатты (mW)
            power_mw = power_uw / 1000.0
            if power_mw > 0: # Дополнительная проверка после деления
                 # Рассчитываем dBm: 10 * log10( P(mW) )
                dbm = 10 * math.log10(power_mw)
                # logger.info(f":::::::Input uW={power_uw}, mW={power_mw}, Output dBm={dbm}:::::::")
                return dbm
            else:
                 # Логарифм от нуля или отрицательного числа не определен
                 logger.warning(f"Cannot calculate dBm for non-positive mW value derived from uW={power_uw}")
                 # Возвращаем отрицательную бесконечность как представление очень низкой мощности
                 return float('-inf')
        elif power_uw == 0:
             logger.warning("Cannot calculate dBm for zero power input.")
             return float('-inf') # dBm для 0 mW стремится к -inf
        else: # power_uw < 0
             logger.warning(f"Cannot calculate dBm for negative power input: {power_uw} uW")
             return None # Некорректное значение мощности
    except (ValueError, TypeError) as e:
        logger.error(f"Error converting '{value_str}' to float for dBm calculation: {e}")
        return None # Возвращаем None при ошибке конвертации


class SNMPUpdater:
    """
    Класс для выполнения SNMP запросов и обновления данных конкретного свитча.
    """
    def __init__(self, selected_switch, snmp_community):
        self.selected_switch = selected_switch
        self.ip = selected_switch.ip
        self.hostname = selected_switch.hostname # Для логирования
        self.snmp_community = snmp_community

        if selected_switch.model:
            self.model = selected_switch.model.device_model
        else:
            self.model = None
            logger.warning(f"Switch {self.ip} ({self.hostname}) has no associated model.")

        # Получаем OIDы; будут None, если модель не найдена или не определена
        self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID = self.get_snmp_oids()

        # Используем глобальный логгер
        # self.logger = logger

    def get_snmp_oids(self):
        """
        Возвращает кортеж (TX_OID, RX_OID, VENDOR_OID, PN_OID) на основе модели свитча.
        Возвращает (None, None, None, None), если модель не найдена или None.
        """
        if not self.model:
            logger.error(f"Cannot determine OIDs for switch {self.ip} ({self.hostname}) because model is missing.")
            return (None, None, None, None)

        # Словарь OIDов для разных моделей
        oid_map = {
            # Модели и их OIDы... (полный список как в вашем оригинальном коде)
            'MES3500-24S': ('1.3.6.1.4.1.890.1.15.3.84.1.2.1.6.28.4', '1.3.6.1.4.1.890.1.15.3.84.1.2.1.6.28.5', '1.3.6.1.4.1.890.1.15.3.84.1.1.1.2.28', '1.3.6.1.4.1.890.1.15.3.84.1.1.1.4.28'),
            'MES2428': ('iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.28.4.1', 'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.28.5.1', 'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.28', 'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.28'),
            'MES2408': ('iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.10.4.1', 'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.10.5.1', 'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.10', 'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.10'),
            'MES2428B': ('iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.28.4.1', 'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.28.5.1', 'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.28', 'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.28'),
            'MES2408B': ('iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.10.4.1', 'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.10.5.1', 'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.10', 'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.10'),
            'MES3500-24': ('iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.28.4', 'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.28.5', 'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.28', 'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.28'),
            'MES3500-10': ('iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.10.4', 'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.10.5', 'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.10', 'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.10'),
            'GS3700-24HP': ('iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.28.4', 'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.28.5', 'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.28', 'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.28'),
            'MES1124MB': ('iso.3.6.1.4.1.89.90.1.2.1.3.49.8', 'iso.3.6.1.4.1.89.90.1.2.1.3.49.9', 'iso.3.6.1.4.1.35265.1.23.53.1.1.1.5', None), # PN OID отсутствует?
            'MGS3520-28': ('iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.28.4', 'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.28.5', 'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.28', 'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.28'),
            'SNR-S2985G-24TC': ('iso.3.6.1.4.1.40418.7.100.30.1.1.22.28', 'iso.3.6.1.4.1.40418.7.100.30.1.1.17.28', None, None), # Vendor/PN отсутствуют?
            'SNR-S2985G-8T': ('iso.3.6.1.4.1.40418.7.100.30.1.1.22.10', 'iso.3.6.1.4.1.40418.7.100.30.1.1.17.10', None, None),
            'SNR-S2982G-24T': ('iso.3.6.1.4.1.40418.7.100.30.1.1.22.28', 'iso.3.6.1.4.1.40418.7.100.30.1.1.17.28', None, None),
            'T2600G-28TS': ('iso.3.6.1.4.1.11863.6.96.1.7.1.1.8.49177', 'iso.3.6.1.4.1.11863.6.96.1.7.1.1.8.49177', None, None), # TX и RX OID одинаковые? Проверить!
            'S3328TP-SI': ('iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.67240014', 'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.67240014', None, None),
            'S3328TP-EI': ('iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.67240014', 'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.67240014', None, None),
            # Добавьте другие модели по необходимости
        }
        # OIDы по умолчанию, если модель не найдена в словаре
        default_oids = ('iso.3.6.1.4.1.2011.5.14.6.4.1.4.234881088', # Пример TX по умолчанию
                        'iso.3.6.1.4.1.2011.5.14.6.4.1.5.234881088', # Пример RX по умолчанию
                        None,
                        None)

        oids = oid_map.get(self.model, default_oids)

        if oids == default_oids:
            logger.warning(f"Using default OIDs for unsupported model: {self.model} on switch {self.ip} ({self.hostname})")

        return oids

    def perform_snmpwalk(self, oid):
        """
        Выполняет SNMP GETNEXT (имитация walk) для заданного OID.
        Возвращает список строк со значениями или пустой список при ошибке/таймауте/отсутствии OID.
        """
        if not oid:
            # logger.debug(f"Skipping SNMP walk for IP {self.ip} due to missing OID.")
            return []

        # logger.debug(f"Starting SNMP walk for IP {self.ip}, OID: {oid}")
        snmp_response_values = []
        try:
            iterator = nextCmd( # Используем nextCmd для walk
                SnmpEngine(),
                CommunityData(self.snmp_community, mpModel=0), # mpModel=0 для SNMPv1/v2c
                UdpTransportTarget((self.ip, 161), timeout=2, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False # Важно для walk
            )

            for errorIndication, errorStatus, errorIndex, varBinds in iterator:
                if errorIndication:
                    if 'timed out' in str(errorIndication).lower():
                        logger.warning(f"SNMP timeout for {self.ip} ({self.hostname}) (OID: {oid}).")
                    elif 'no response' in str(errorIndication).lower():
                        logger.warning(f"No SNMP response from {self.ip} ({self.hostname}) (OID: {oid}).")
                    else:
                        logger.error(f"SNMP error for {self.ip} ({self.hostname}) (OID: {oid}): {errorIndication}")
                    return [] # Возвращаем пустой список при ошибке

                elif errorStatus:
                    logger.error(
                        f"SNMP error status for {self.ip} ({self.hostname}) (OID: {oid}): "
                        f"{errorStatus.prettyPrint()} at "
                        f"{errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
                    )
                    return [] # Возвращаем пустой список при ошибке статуса

                else:
                    # varBinds содержит список кортежей (OID, значение)
                    for varBind in varBinds:
                        response_oid = varBind[0]
                        response_value = varBind[1]

                        # Проверяем, что ответный OID начинается с запрошенного OID
                        # (или его префикса, если OID был без индекса)
                        # Это важно, чтобы не "уйти" далеко по дереву MIB
                        if str(response_oid).startswith(oid):
                            # Добавляем только значение, преобразованное в строку
                            snmp_response_values.append(str(response_value))
                        else:
                            # Если OID ответа уже не в запрошенной ветке, завершаем walk
                            # logger.debug(f"Walk finished for OID {oid} on {self.ip}. Response OID {response_oid} outside branch.")
                            return snmp_response_values

            # Если цикл завершился без выхода из ветки OID (например, дошли до конца MIB)
            # logger.debug(f"SNMP walk successful for {self.ip} ({self.hostname}), OID: {oid}. Responses: {snmp_response_values}")
            return snmp_response_values

        except Exception as e:
            # Ловим другие возможные ошибки (сетевые, PySNMP и т.д.)
            logger.error(f"Exception during SNMP walk for {self.ip} ({self.hostname}) (OID: {oid}): {e}", exc_info=False)
            return []


    async def update_switch_data_async(self):
        """
        Асинхронно получает и обновляет данные свитча через SNMP.
        """
        # Проверяем наличие обязательных OIDов перед запросами
        if not self.TX_SIGNAL_OID or not self.RX_SIGNAL_OID:
            logger.warning(f"Skipping update for {self.ip} ({self.hostname}): Missing essential TX/RX OIDs for model '{self.model}'.")
            return

        loop = asyncio.get_event_loop()
        results = {} # Словарь для хранения результатов

        try:
            # Создаем задачи для конкурентного выполнения SNMP запросов
            tasks = {
                'tx': loop.run_in_executor(None, self.perform_snmpwalk, self.TX_SIGNAL_OID),
                'rx': loop.run_in_executor(None, self.perform_snmpwalk, self.RX_SIGNAL_OID)
            }
            # Добавляем задачи для опциональных OIDов, если они есть
            if self.SFP_VENDOR_OID:
                tasks['vendor'] = loop.run_in_executor(None, self.perform_snmpwalk, self.SFP_VENDOR_OID)
            if self.PART_NUMBER_OID:
                tasks['part'] = loop.run_in_executor(None, self.perform_snmpwalk, self.PART_NUMBER_OID)

            # Ожидаем завершения всех задач
            task_results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            # Сопоставляем результаты с ключами задач
            results = dict(zip(tasks.keys(), task_results))

            # Обрабатываем результаты и логируем ошибки
            tx_signal_raw = []
            if 'tx' in results:
                if isinstance(results['tx'], Exception):
                    logger.error(f"Error fetching TX signal for {self.ip} ({self.hostname}): {results['tx']}")
                else:
                    tx_signal_raw = results['tx']
            # logger.info(f"{self.ip} - TX_SIGNAL_raw: {tx_signal_raw}") # Отладка

            rx_signal_raw = []
            if 'rx' in results:
                if isinstance(results['rx'], Exception):
                    logger.error(f"Error fetching RX signal for {self.ip} ({self.hostname}): {results['rx']}")
                else:
                    rx_signal_raw = results['rx']
            # logger.info(f"{self.ip} - RX_SIGNAL_raw: {rx_signal_raw}") # Отладка

            sfp_vendor_raw = []
            if 'vendor' in results:
                if isinstance(results['vendor'], Exception):
                    logger.error(f"Error fetching SFP Vendor for {self.ip} ({self.hostname}): {results['vendor']}")
                else:
                    sfp_vendor_raw = results['vendor']
            # logger.info(f"{self.ip} - SFP_VENDOR_raw: {sfp_vendor_raw}") # Отладка

            part_number_raw = []
            if 'part' in results:
                if isinstance(results['part'], Exception):
                    logger.error(f"Error fetching Part Number for {self.ip} ({self.hostname}): {results['part']}")
                else:
                    part_number_raw = results['part']
            # logger.info(f"{self.ip} - PART_NUMBER_raw: {part_number_raw}") # Отладка

            # --- Извлечение и обработка данных ---
            tx_signal_val_str = self.extract_first_value(tx_signal_raw)
            rx_signal_val_str = self.extract_first_value(rx_signal_raw)
            sfp_vendor_val_str = self.extract_first_value(sfp_vendor_raw)
            part_number_val_str = self.extract_first_value(part_number_raw)

            # --- Обработка сигналов ---
            processed_tx = None
            processed_rx = None

            # Нормализуем значения сигналов в зависимости от модели
            if tx_signal_val_str is not None and rx_signal_val_str is not None:
                try:
                    if self.model and ('3328' in self.model or 'T2600G' in self.model):
                        # Конвертация из uW в dBm
                        # logger.info(f"{self.ip} - Converting to dBm. Raw TX='{tx_signal_val_str}', Raw RX='{rx_signal_val_str}'")
                        processed_tx = mw_to_dbm(tx_signal_val_str)
                        processed_rx = mw_to_dbm(rx_signal_val_str)
                        # logger.info(f"{self.ip} - Converted TX dBm={processed_tx}, RX dBm={processed_rx}")

                    elif self.model and ('SNR' in self.model):
                        # Предполагаем, что SNR возвращает dBm * 10 или просто dBm?
                        # Уточнить формат! Пока считаем, что это float dBm.
                        processed_tx = float(tx_signal_val_str)
                        processed_rx = float(rx_signal_val_str)

                    elif self.model and ('3500' in self.model or 'GS3700' in self.model or 'MGS3520-28' in self.model):
                        # Предполагаем 0.01 dBm (значение / 100)
                        processed_tx = float(tx_signal_val_str) / 100.0
                        processed_rx = float(rx_signal_val_str) / 100.0

                    else:
                        # Поведение по умолчанию: предполагаем 0.001 dBm (значение / 1000)
                        # Проверить это предположение для остальных моделей!
                        processed_tx = float(tx_signal_val_str) / 1000.0
                        processed_rx = float(rx_signal_val_str) / 1000.0

                except (ValueError, TypeError) as e:
                    logger.warning(f"{self.ip} ({self.hostname}) - Error processing signal values: TX='{tx_signal_val_str}', RX='{rx_signal_val_str}'. Error: {e}")
                    processed_tx = None
                    processed_rx = None

            # --- Обновление объекта Switch ---
            switch = self.selected_switch

            # Округляем до 2 знаков после запятой, если значение - конечное число
            switch.tx_signal = round(processed_tx, 2) if processed_tx is not None and math.isfinite(processed_tx) else None
            switch.rx_signal = round(processed_rx, 2) if processed_rx is not None and math.isfinite(processed_rx) else None

            # Обновляем информацию SFP (None, если значение пустое или не получено)
            switch.sfp_vendor = sfp_vendor_val_str if sfp_vendor_val_str else None
            switch.part_number = part_number_val_str if part_number_val_str else None

            # --- Сохранение данных ---
            try:
                # logger.info(f"Attempting to save switch data for: {switch.hostname} ({switch.ip})")
                # Выполняем сохранение в отдельном потоке, чтобы не блокировать event loop
                await loop.run_in_executor(None, switch.save)
                logger.info(f"Successfully saved switch data for: {switch.hostname} ({switch.ip}) TX:{switch.tx_signal} RX:{switch.rx_signal}")
            except Exception as e:
                logger.error(f"Error saving data for switch {switch.ip} ({switch.hostname}): {e}", exc_info=True)

        except Exception as e:
            # Ловим общие ошибки во время асинхронного выполнения
            logger.error(f"General error during async update for {self.ip} ({self.hostname}): {e}", exc_info=True)


    def update_switch_data(self):
        """
        Синхронная обертка для запуска асинхронного обновления данных свитча.
        Обрабатывает получение или создание event loop.
        """
        try:
            # Получаем текущий event loop или создаем новый, если нужно
            loop = asyncio.get_event_loop_policy().get_event_loop()
            if loop.is_closed():
                # logger.debug("Event loop was closed, creating a new one.")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # Запускаем и закрываем цикл, который мы создали
                loop.run_until_complete(self.update_switch_data_async())
                # loop.close() # Закрывать стоит, только если точно уверены, что он больше не нужен
            else:
                 # Если цикл уже существует и открыт, просто запускаем корутину
                 loop.run_until_complete(self.update_switch_data_async())

        except RuntimeError as e:
            if "Cannot run coroutine in a closed event loop" in str(e):
                logger.warning(f"Attempted to run on a closed event loop for {self.ip}. Creating a new one.")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.update_switch_data_async())
                # loop.close()
            elif "There is no current event loop in thread" in str(e):
                logger.warning(f"No event loop in current thread for {self.ip}. Creating a new one.")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.update_switch_data_async())
                # loop.close()
            else:
                 logger.error(f"RuntimeError in update_switch_data for {self.ip} ({self.hostname}): {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in update_switch_data wrapper for {self.ip} ({self.hostname}): {e}", exc_info=True)


    def extract_first_value(self, snmp_response_list):
        """
        Извлекает первое непустое значение из списка ответов SNMP.
        Возвращает строку или None.
        """
        if snmp_response_list:
            first_value = str(snmp_response_list[0]).strip()
            # Возвращаем None, если строка пустая или равна 'none' (без учета регистра)
            # Некоторые устройства могут возвращать пустую строку или строку "None"
            if first_value and first_value.lower() != 'none':
                return first_value
        return None


# --- Класс Управляющей Команды Django ---

class Command(BaseCommand):
    """
    Django management command для обновления данных свитчей через SNMP.
    Фильтрует свитчи по жестко заданной подсети 10.47.0.0/16.
    """
    help = 'Update switch SNMP data for switches ONLY within the 10.47.0.0/16 subnet'

    def add_arguments(self, parser):
        # Добавляем только аргумент для community, подсеть жестко задана
        parser.add_argument(
            '--community',
            default='snmp2netread', # Значение по умолчанию
            help='SNMP community string to use.'
        )

    def handle(self, *args, **options):
        snmp_community = options['community'] # Получаем community из аргументов

        # --- Жестко заданная подсеть ---
        hardcoded_subnet_str = "10.47.0.0/16"
        allowed_networks = []
        try:
            # Создаем объект IPv4Network для нашей подсети
            network = IPv4Network(hardcoded_subnet_str, strict=False)
            allowed_networks.append(network)
            logger.info(f"Filtering switches by hardcoded subnet: {network}")
        except ValueError:
            # Критическая ошибка, если строка подсети невалидна
            logger.critical(f"FATAL: Invalid hardcoded subnet string '{hardcoded_subnet_str}'. Cannot proceed.")
            return # Прерываем выполнение команды

        # --- Основной цикл ---
        # Оставьте `while True`, если команда должна работать непрерывно.
        # Добавьте `import time` и `time.sleep(seconds)` в конце цикла для паузы.
        # Уберите `while True` и `break` для однократного выполнения.
        while True:
            logger.info(f"Starting switch update cycle for subnet {hardcoded_subnet_str}...")
            # Получаем свитчи из БД со статусом True
            selected_switches = Switch.objects.filter(status=True).order_by('-pk')
            processed_count = 0
            skipped_count = 0

            # Итерируем по выбранным свитчам
            for selected_switch in selected_switches:
                try:
                    # --- Проверка IP адреса ---
                    switch_ip_str = selected_switch.ip
                    if not switch_ip_str:
                        logger.warning(f"Switch hostname '{selected_switch.hostname}' (PK: {selected_switch.pk}) has no IP address. Skipping.")
                        skipped_count += 1
                        continue

                    try:
                        # Преобразуем строку IP в объект IP-адреса
                        switch_ip = parse_ip_address(switch_ip_str)
                    except ValueError:
                        logger.error(f"Invalid IP address format for switch '{selected_switch.hostname}': '{switch_ip_str}'. Skipping.")
                        skipped_count += 1
                        continue

                    # --- Фильтрация по подсети ---
                    # Проверяем, входит ли IP свитча в нашу жестко заданную подсеть
                    # allowed_networks[0] содержит единственный объект IPv4Network("10.47.0.0/16")
                    if switch_ip in allowed_networks[0]:
                        # IP подходит, обрабатываем свитч
                        logger.debug(f"Processing switch: {selected_switch.hostname} ({switch_ip}) - IP is within the allowed subnet {hardcoded_subnet_str}.")

                        # Создаем экземпляр SNMPUpdater и запускаем обновление
                        snmp_updater = SNMPUpdater(selected_switch, snmp_community)
                        snmp_updater.update_switch_data() # Запускает асинхронную логику синхронно

                        processed_count += 1
                    else:
                        # IP не входит в подсеть, пропускаем
                        logger.info(f"Skipping switch: {selected_switch.hostname} ({switch_ip}) - IP is outside the hardcoded subnet {hardcoded_subnet_str}.")
                        skipped_count += 1
                        continue # Переходим к следующему свитчу

                except Exception as e:
                    # Ловим неожиданные ошибки при обработке одного свитча,
                    # чтобы они не остановили всю команду
                    logger.error(f"Unexpected error processing switch {selected_switch.hostname} ({selected_switch.ip}): {e}", exc_info=True)
                    skipped_count += 1 # Считаем как пропущенный из-за ошибки

            # Логируем итоги цикла
            logger.info(f"Switch update cycle finished. Processed: {processed_count}, Skipped (outside subnet or error): {skipped_count}.")

            # --- Управление циклом ---
            # Если команда должна выполниться только один раз, используйте break
            logger.info("Command finished one cycle.")
            break

            # Если нужен непрерывный цикл с паузой:
            # import time
            # sleep_duration = 300 # Пауза 5 минут
            # logger.info(f"Sleeping for {sleep_duration} seconds before next cycle...")
            # time.sleep(sleep_duration)