import asyncio
import logging
import math
import time
import os
from typing import Dict, List, Any, Optional, Tuple

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from pysnmp.hlapi.asyncio import (
    getCmd, nextCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
)
from pysnmp.smi import builder, view, compiler, error as pysnmp_error, rfc1902

# --- Предполагаемые импорты ваших моделей ---
# Замените 'your_snmp_app' на имя вашего Django приложения
try:
    from snmp.models import Switch, SwitchModel, SwitchesPorts, Vendor
except ImportError:
    print("ERROR: Could not import models from 'snmp.models'. Please ensure the app name and models are correct.")
    raise

# --- Базовая настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SNMP_OPTICAL_MIB")

# --- Основные символьные имена стандартных MIB ---
IF_ENTRY = 'IF-MIB::ifEntry'
IF_INDEX = 'IF-MIB::ifIndex'
IF_DESCR = 'IF-MIB::ifDescr'
IF_TYPE = 'IF-MIB::ifType'
IF_ALIAS = 'IF-MIB::ifAlias'
IF_NAME = 'ifName' # Часто не требует префикса
IF_ADMIN_STATUS = 'IF-MIB::ifAdminStatus'
IF_OPER_STATUS = 'IF-MIB::ifOperStatus'
IF_LAST_CHANGE = 'IF-MIB::ifLastChange'
IF_HIGH_SPEED = 'IF-MIB::ifHighSpeed'
IF_SPEED = 'IF-MIB::ifSpeed'
ENTITY_PHYSICAL_ENTRY = 'ENTITY-MIB::entPhysicalEntry'
ENT_PHYSICAL_INDEX = 'ENTITY-MIB::entPhysicalIndex'
ENT_PHYSICAL_DESCR = 'ENTITY-MIB::entPhysicalDescr'
ENT_PHYSICAL_CLASS = 'ENTITY-MIB::entPhysicalClass'
ENT_PHYSICAL_NAME = 'ENTITY-MIB::entPhysicalName'
ENT_ALIAS_MAPPING_IDENTIFIER = 'ENTITY-MIB::entAliasMappingIdentifier'
ENTITY_SENSOR_VALUE = 'ENTITY-SENSOR-MIB::entPhySensorValue'
ENTITY_SENSOR_TYPE = 'ENTITY-SENSOR-MIB::entPhySensorType'
ENTITY_SENSOR_SCALE = 'ENTITY-SENSOR-MIB::entPhySensorScale'
ENTITY_SENSOR_PRECISION = 'ENTITY-SENSOR-MIB::entPhySensorPrecision'
ENTITY_SENSOR_UNITS = 'ENTITY-SENSOR-MIB::entPhySensorUnitsDisplay'

# --- Типы интерфейсов для определения оптики ---
POTENTIALLY_OPTICAL_IFTYPES = { 6, 32, 53, 62, 69, 117, 127, 129, 131, 135, 136, 161, 180 }

# --- Глобальные MIB объекты ---
mibBuilder = builder.MibBuilder()
mibView = view.MibViewController(mibBuilder)

# --- Критичная настройка: Загрузка MIB ---
try:
    mib_dirs = getattr(settings, 'SNMP_MIBS_DIRS', [])
    if mib_dirs:
        compiler.addMibCompiler(mibBuilder, sources=mib_dirs)
        logger.info(f"Added MIB directories: {mib_dirs}")
    else:
        logger.warning("settings.SNMP_MIBS_DIRS is not defined or empty. MIB resolution may fail.")

    mib_sources = getattr(settings, 'SNMP_MIBS_SOURCES', [])
    if mib_sources:
         compiler.addMibCompiler(mibBuilder, sources=mib_sources)
         logger.info(f"Added MIB sources: {mib_sources}")

    # Предзагрузка для ускорения
    mibBuilder.loadModules('SNMPv2-MIB', 'IF-MIB', 'ENTITY-MIB', 'ENTITY-SENSOR-MIB')
    logger.info("Preloaded standard MIBs: SNMPv2-MIB, IF-MIB, ENTITY-MIB, ENTITY-SENSOR-MIB")

except pysnmp_error.SmiError as e:
    logger.critical(f"MIB controller initialization failed: {e}. Ensure MIB files are accessible in SNMP_MIBS_DIRS.", exc_info=True)
    # Без MIB контроллера команда бесполезна
    raise SystemExit("Critical MIB Initialization Failure")


def mw_to_dbm(mw: float) -> Optional[float]:
    if mw is None: return None
    try:
        mw = float(mw)
        if mw > 0:
            if mw > 10000: mw = mw / 1000.0 # Эвристика для uW
            dbm = 10 * math.log10(mw / 1000.0)
            return round(dbm, 2)
        elif mw == 0: return -99.0 # Или None
        else: return None
    except (ValueError, TypeError, OverflowError): return None


def parse_snmp_value(mib_var: Tuple, switch_model: Optional[SwitchModel] = None) -> Any:
    oid, val = mib_var
    if val is None or isinstance(val, (rfc1902.NoSuchObject, rfc1902.NoSuchInstance)):
        return None

    mib_node, node_name, units, syntax = None, str(oid), None, None
    try:
        mib_node_tuple = mibView.getNodeName(oid)
        if mib_node_tuple:
             mod_name, node_sym, suffix = mib_node_tuple
             node_name = f"{mod_name}::{node_sym}{suffix}"
             mib_node, = mibBuilder.importSymbols(mod_name, node_sym)
             if hasattr(mib_node, 'syntax'): syntax = mib_node.syntax
             if hasattr(mib_node, 'units'): units = mib_node.getUnits()
    except pysnmp_error.SmiError:
        pass # Не удалось разрешить имя MIB

    raw_value_str = val.prettyPrint()
    parsed_value = None
    target_unit_config = 'auto'
    actual_source_unit = 'unknown'
    is_string, is_power, is_temp = False, False, False

    if switch_model:
        config = {
            'tx_power': (switch_model.tx_power_object, switch_model.power_unit),
            'rx_power': (switch_model.rx_power_object, switch_model.power_unit),
            'temperature': (switch_model.temperature_object, switch_model.temperature_unit),
            'sfp_vendor': (switch_model.sfp_vendor_object, 'string'),
            'part_num': (switch_model.part_num_object, 'string'),
            'serial_num': (switch_model.serial_num_object, 'string'),
            'voltage': (switch_model.voltage_object, 'auto'),
        }
        for key, (obj_name, unit_conf) in config.items():
            if obj_name and (obj_name in node_name or node_name.endswith(obj_name)):
                 if 'power' in key: is_power = True
                 if 'temp' in key: is_temp = True
                 if unit_conf == 'string': is_string = True
                 target_unit_config = unit_conf
                 if target_unit_config != 'auto' and target_unit_config != 'string':
                     actual_source_unit = target_unit_config # Приоритет у конфига
                 break

    # Определение типа данных, если не из конфига
    if not is_string and not is_power and not is_temp:
        if syntax and 'OctetString' in str(syntax.__class__):
             if all(32 <= ord(c) < 127 for c in val.asOctets()): is_string = True
        if any(k in node_name for k in ['entPhysicalVendor', 'entPhysicalModel', 'entPhysicalSerial', 'ifAlias', 'ifDescr', 'ifName']):
            is_string = True
        if ENTITY_SENSOR_VALUE in node_name:
             actual_source_unit = 'from_sensor_mib'
             if units and 'watt' in units.lower(): is_power = True
             if units and 'celsius' in units.lower(): is_temp = True

    # Парсинг строк
    if is_string:
        str_value = raw_value_str
        if len(str_value) >= 2 and str_value.startswith('"') and str_value.endswith('"'):
            str_value = str_value[1:-1]
        parsed_value = ''.join(c for c in str_value if c.isprintable()).strip()
        return parsed_value or None

    # Парсинг чисел
    try:
        num_value_str = raw_value_str.split()[0]
        num_value = float(num_value_str)
        parsed_value = num_value

        # Определяем единицы источника из MIB, если не из конфига
        if actual_source_unit == 'unknown' and units:
             unit_lower = units.lower()
             if 'dbm' in unit_lower: actual_source_unit = 'dbm'
             elif 'watt' in unit_lower: actual_source_unit = 'mw' # Предполагаем mW
             elif 'celsius' in unit_lower: actual_source_unit = 'celsius'

        # Конвертация
        if is_power:
            target_unit = 'dbm'
            converted = None
            if actual_source_unit == 'dbm': converted = round(num_value, 2)
            elif actual_source_unit == 'mw': converted = mw_to_dbm(num_value)
            elif actual_source_unit == 'scaled_dbm_100': converted = round(num_value / 100.0, 2)
            elif actual_source_unit == 'scaled_mw_1000': converted = mw_to_dbm(num_value / 1000.0) # uW
            elif actual_source_unit == 'scaled_mw_10': converted = mw_to_dbm(num_value / 10.0) # 0.1 uW
            elif actual_source_unit in ['unknown', 'auto', 'from_sensor_mib']:
                 # Пробуем угадать (менее надежно)
                 if -30 < num_value < 15: converted = round(num_value, 2)
                 elif abs(num_value) > 500 and abs(num_value) < 5000: converted = round(num_value / 100.0, 2)
                 elif num_value > 0 and num_value < 100: converted = mw_to_dbm(num_value)
                 elif num_value > 100: converted = mw_to_dbm(num_value/1000.0)
            parsed_value = converted
        elif is_temp:
            converted = None
            if actual_source_unit == 'celsius': converted = round(num_value, 2)
            elif actual_source_unit == 'scaled_celsius_100': converted = round(num_value / 100.0, 2)
            elif actual_source_unit in ['unknown', 'auto', 'from_sensor_mib']:
                 if abs(num_value) > 1000: converted = round(num_value / 100.0, 2)
                 else: converted = round(num_value, 2)
            parsed_value = converted
        elif isinstance(parsed_value, float):
            parsed_value = round(parsed_value, 2)

        return parsed_value
    except (ValueError, TypeError, OverflowError):
        return None


async def snmp_get_symbolic(snmp_engine: SnmpEngine, community: str, target: str, port: int, *mib_symbol: Any, timeout: int = 2, retries: int = 1) -> Optional[Tuple[Any, Any]]:
    try:
        var_binds = [ObjectType(ObjectIdentity(*mib_symbol).resolveWithMib(mibView))]
    except pysnmp_error.SmiError as e:
        # Критично: Ошибка разрешения MIB символа
        logger.error(f"MIB resolution failed for {mib_symbol} on {target}: {e}")
        return None

    errorIndication, errorStatus, errorIndex, varBindsRet = await getCmd(
        snmp_engine, CommunityData(community, mpModel=1), UdpTransportTarget((target, port), timeout=timeout, retries=retries),
        ContextData(), *var_binds
    )
    if errorIndication:
        log_level = logging.WARNING if 'timeout' not in str(errorIndication).lower() else logging.DEBUG
        logger.log(log_level, f"SNMP GET failed for {target} symbol {mib_symbol}: {errorIndication}")
        return None
    elif errorStatus:
        if 'noSuch' not in errorStatus.prettyPrint():
             resolved_oid = varBindsRet[int(errorIndex) - 1][0] if errorIndex and varBindsRet else '?'
             logger.warning(f"SNMP GET error for {target} symbol {mib_symbol}: {errorStatus.prettyPrint()} at {resolved_oid}")
        return None
    else:
        return varBindsRet[0] if varBindsRet else None


async def snmp_walk_symbolic(snmp_engine: SnmpEngine, community: str, target: str, port: int, *base_mib_symbol: Any, timeout: int = 5, retries: int = 1) -> Dict[str, Tuple[Any, Any]]:
    results = {}
    try:
        base_obj_type = ObjectType(ObjectIdentity(*base_mib_symbol).resolveWithMib(mibView))
        base_oid_resolved = base_obj_type[0]
    except pysnmp_error.SmiError as e:
        # Критично: Ошибка разрешения MIB символа для базы walk
        logger.error(f"MIB resolution failed for WALK base {base_mib_symbol} on {target}: {e}")
        return {}

    current_obj_type = base_obj_type
    transport = UdpTransportTarget((target, port), timeout=timeout, retries=retries)
    community_data = CommunityData(community, mpModel=1)

    try:
        while True:
            errorIndication, errorStatus, errorIndex, varBinds = await nextCmd(
                snmp_engine, community_data, transport, ContextData(),
                current_obj_type, lexicographicMode=True, ignoreNonIncreasingOid=True
            )
            if errorIndication: logger.warning(f"SNMP WALK failed for {target} base {base_mib_symbol}: {errorIndication}"); break
            elif errorStatus: logger.debug(f"SNMP WALK error for {target} base {base_mib_symbol}: {errorStatus.prettyPrint()}"); break
            if not varBinds or not varBinds[0][0].isPrefixOf(base_oid_resolved): break

            oid, value = varBinds[0]
            results[str(oid)] = (oid, value)
            current_obj_type = ObjectType(oid)
    except Exception as e:
         logger.error(f"Exception during SNMP WALK for {target} base {base_mib_symbol}: {e}", exc_info=True)

    return results


class SNMPDevicePoller:
    def __init__(self, switch: Switch, snmp_port: int = 161, timeout: int = 5, retries: int = 1):
        self.switch = switch
        self.ip = switch.ip
        self.community = switch.snmp_community_ro or 'public'
        self.port = snmp_port
        self.timeout = timeout
        self.retries = retries
        self.snmp_engine = SnmpEngine()
        self.mib_builder = mibBuilder
        self.mib_view = mibView
        self.switch_model: Optional[SwitchModel] = switch.model
        self.symbolic_config: Dict[str, Optional[str]] = {}
        self.interfaces: Dict[int, Dict[str, Any]] = {}
        self.entity_map: Dict[int, int] = {}

    async def _load_mibs_for_model(self):
        if not self.switch_model or not self.switch_model.required_mibs: return True
        mibs_to_load = [mib.strip() for mib in self.switch_model.required_mibs.split(',') if mib.strip()]
        loaded_successfully = True
        for mib_name in mibs_to_load:
            try:
                # Критично: Загрузка вендорских MIB
                self.mib_builder.loadModules(mib_name)
                logger.info(f"[{self.ip}] Loaded MIB module: {mib_name}")
            except pysnmp_error.SmiError as e:
                logger.error(f"[{self.ip}] Failed to load MIB module {mib_name}: {e}")
                loaded_successfully = False
        return loaded_successfully

    def _load_symbolic_config(self):
        if not self.switch_model: return False
        self.symbolic_config = {
            'tx_power': self.switch_model.tx_power_object, 'rx_power': self.switch_model.rx_power_object,
            'sfp_vendor': self.switch_model.sfp_vendor_object, 'part_num': self.switch_model.part_num_object,
            'serial_num': self.switch_model.serial_num_object, 'temperature': self.switch_model.temperature_object,
            'voltage': self.switch_model.voltage_object, 'ddm_index_type': self.switch_model.ddm_index_type,
            'power_unit': self.switch_model.power_unit, 'temperature_unit': self.switch_model.temperature_unit,
        }
        logger.info(f"[{self.ip}] Loaded symbolic config for model '{self.switch_model.device_model}'")
        return True

    async def _get_physical_entity_mapping(self):
        # Критично: Маппинг ifIndex на entPhysicalIndex через стандартный механизм
        logger.debug(f"[{self.ip}] Fetching entAliasMappingIdentifier...")
        self.entity_map = {}
        walk_results = await snmp_walk_symbolic(self.snmp_engine, self.community, self.ip, self.port, ENT_ALIAS_MAPPING_IDENTIFIER)
        if not walk_results:
            logger.warning(f"[{self.ip}] Failed to get entAliasMappingIdentifier. Trying fallback mapping.")
            await self._get_physical_entity_mapping_fallback()
            return

        try:
            expected_ifindex_base_oid, = ObjectIdentity(IF_INDEX).resolveWithMib(mibView)
            for oid_str, (oid_obj, value_obj) in walk_results.items():
                try:
                    ent_physical_index = int(oid_obj[-1])
                    if isinstance(value_obj, rfc1902.ObjectIdentifier) and value_obj.isPrefixOf(expected_ifindex_base_oid):
                        if_index = int(value_obj[-1])
                        self.entity_map[if_index] = ent_physical_index
                        logger.debug(f"[{self.ip}] Mapped ifIndex {if_index} to entPhysicalIndex {ent_physical_index}")
                except (IndexError, ValueError, TypeError): pass # Игнорируем ошибки парсинга отдельной записи
        except pysnmp_error.SmiError:
             logger.error(f"[{self.ip}] Failed to resolve IF-MIB::ifIndex for mapping.")
        logger.info(f"[{self.ip}] Built entity map. Found {len(self.entity_map)} mappings.")

    async def _get_physical_entity_mapping_fallback(self):
        # Альтернативный маппинг по именам (менее надежный)
        if not self.interfaces: await self._get_interfaces()
        if_name_map = {idx: data.get('name') or data.get('description') for idx, data in self.interfaces.items()}
        entity_walk_tasks = {
            'name': snmp_walk_symbolic(self.snmp_engine, self.community, self.ip, self.port, ENT_PHYSICAL_NAME),
            'descr': snmp_walk_symbolic(self.snmp_engine, self.community, self.ip, self.port, ENT_PHYSICAL_DESCR),
            'class': snmp_walk_symbolic(self.snmp_engine, self.community, self.ip, self.port, ENT_PHYSICAL_CLASS),
        }
        entity_results = await asyncio.gather(*entity_walk_tasks.values())
        entity_data = {}
        # ... (парсинг результатов walk'а по entPhysical*) ...
        for key, data in zip(entity_walk_tasks.keys(), entity_results):
             if not isinstance(data, dict): continue
             for oid_str, (oid_obj, value_obj) in data.items():
                 try:
                     ent_idx = int(oid_obj[-1])
                     if ent_idx not in entity_data: entity_data[ent_idx] = {}
                     parsed_val = parse_snmp_value((oid_obj, value_obj), None)
                     if key == 'class' : parsed_val = int(parsed_val)
                     entity_data[ent_idx][key] = parsed_val
                 except: pass
        # Сопоставление
        for if_idx, if_name in if_name_map.items():
            if not if_name: continue
            for ent_idx, ent_info in entity_data.items():
                if ent_info.get('class') == 10: # Ищем порт
                    ent_name = ent_info.get('name') or ent_info.get('descr')
                    if ent_name and (if_name == ent_name or if_name in ent_name or ent_name in if_name):
                         if if_idx not in self.entity_map:
                             self.entity_map[if_idx] = ent_idx
                             logger.debug(f"[{self.ip}] Fallback mapped ifIndex {if_idx} to entPhysicalIndex {ent_idx}")
                             break
        logger.info(f"[{self.ip}] Fallback mapping complete. Found {len(self.entity_map)} mappings.")


    async def _get_interfaces(self):
        logger.debug(f"[{self.ip}] Fetching interface table (IF-MIB)...")
        self.interfaces = {}
        if_table_results = await snmp_walk_symbolic(self.snmp_engine, self.community, self.ip, self.port, IF_ENTRY, timeout=15)
        if not if_table_results:
            logger.error(f"[{self.ip}] Failed to get IF-MIB::ifEntry data.")
            return False

        processed_interfaces = {}
        for oid_str, (oid_obj, value_obj) in if_table_results.items():
            try:
                mib_node_tuple = self.mib_view.getNodeName(oid_obj)
                if not mib_node_tuple or not mib_node_tuple[2]: continue
                mod_name, node_sym, suffix = mib_node_tuple
                if_index = int(suffix[0])
                if if_index not in processed_interfaces: processed_interfaces[if_index] = {'if_index': if_index}

                col_name = node_sym.prettyPrint()
                parsed_value = parse_snmp_value((oid_obj, value_obj), self.switch_model)

                if col_name in ['ifAdminStatus', 'ifOperStatus', 'ifType'] and parsed_value is not None:
                     try: parsed_value = int(parsed_value)
                     except: parsed_value = None
                elif col_name == 'ifLastChange' and parsed_value is not None:
                     try: parsed_value = int(parsed_value)
                     except: parsed_value = None

                if col_name == 'ifHighSpeed' and parsed_value is not None and int(parsed_value) > 0:
                    processed_interfaces[if_index]['calculated_speed'] = int(parsed_value)
                elif col_name == 'ifSpeed' and 'calculated_speed' not in processed_interfaces.get(if_index, {}):
                     if parsed_value is not None:
                         try: processed_interfaces[if_index]['calculated_speed'] = int(parsed_value) // 1_000_000
                         except: pass
                else:
                     field_map = {'ifName': 'name', 'ifAlias': 'alias', 'ifDescr': 'description',
                                  'ifAdminStatus': 'admin_status', 'ifOperStatus': 'oper_status',
                                  'ifLastChange': 'last_change', 'ifType': 'type'}
                     mapped_field = field_map.get(col_name)
                     if mapped_field: processed_interfaces[if_index][mapped_field] = parsed_value
                     processed_interfaces[if_index][col_name] = parsed_value # Сохраняем и оригинал
            except (pysnmp_error.SmiError, IndexError, ValueError, TypeError) as e:
                logger.warning(f"[{self.ip}] Error processing ifTable entry {oid_str}: {e}")

        # Фильтрация оптики
        for if_index, data in processed_interfaces.items():
            if_type = data.get('type')
            calculated_speed_mbps = data.get('calculated_speed', 0)
            is_optical = False
            if if_type in POTENTIALLY_OPTICAL_IFTYPES: is_optical = True
            elif if_type == 6: # ethernetCsmacd
                 name_lower = (data.get('name') or data.get('description') or "").lower()
                 if calculated_speed_mbps >= 1000 and 'copper' not in name_lower: is_optical = True
                 if any(k in name_lower for k in ['sfp', 'xfp', 'qsfp', 'fiber', 'fibre', 'optic']): is_optical = True
                 if any(k in name_lower for k in ['copper', 'utp', 'rj45']): is_optical = False

            if is_optical:
                data['speed'] = calculated_speed_mbps
                self.interfaces[if_index] = data
                logger.debug(f"[{self.ip}] Identified optical port: ifIndex={if_index}, Speed={calculated_speed_mbps}Mbps")

        logger.info(f"[{self.ip}] Found {len(self.interfaces)} potential optical interfaces.")
        return bool(self.interfaces)

    async def _get_sensor_details(self, ent_physical_index: int) -> Dict[str, Any]:
        # Критично: Получение масштаба/точности/единиц для стандартных сенсоров
        details = {'scale': None, 'precision': None, 'units': None, 'value_factor': 1.0}
        tasks = {
            'scale': snmp_get_symbolic(self.snmp_engine, self.community, self.ip, self.port, ENTITY_SENSOR_SCALE, ent_physical_index),
            'precision': snmp_get_symbolic(self.snmp_engine, self.community, self.ip, self.port, ENTITY_SENSOR_PRECISION, ent_physical_index),
            'units': snmp_get_symbolic(self.snmp_engine, self.community, self.ip, self.port, ENTITY_SENSOR_UNITS, ent_physical_index),
        }
        results = await asyncio.gather(*tasks.values())
        res_map = dict(zip(tasks.keys(), results))
        try:
            if res_map['scale'] and res_map['scale'][1] is not None:
                scale_val = int(res_map['scale'][1])
                scale_map = {1: -12, 2: -9, 3: -6, 4: -3, 5: 0, 6: 3, 7: 6, 8: 9, 9: 12}
                details['scale'] = scale_map.get(scale_val)
            if res_map['precision'] and res_map['precision'][1] is not None:
                details['precision'] = int(res_map['precision'][1])
            if res_map['units'] and res_map['units'][1] is not None:
                details['units'] = parse_snmp_value(res_map['units'], None)

            if details['scale'] is not None: details['value_factor'] = 10**details['scale']
            if details['precision'] is not None: details['value_factor'] *= 10**(-details['precision'])
        except (ValueError, TypeError): pass
        logger.debug(f"[{self.ip}] Sensor {ent_physical_index} details: Units='{details['units']}', Factor={details['value_factor']}")
        return details

    async def _poll_port_data(self, if_index: int) -> Dict[str, Any]:
        port_result = {'if_index': if_index}
        if not self.symbolic_config: return port_result

        ddm_index_type = self.symbolic_config.get('ddm_index_type', 'entPhysicalIndex')
        target_index = if_index if ddm_index_type == 'ifIndex' else self.entity_map.get(if_index)
        if target_index is None:
            if ddm_index_type == 'entPhysicalIndex': logger.warning(f"[{self.ip}] No entPhysicalIndex mapping for ifIndex {if_index}.")
            return port_result # Не можем опросить без индекса

        logger.debug(f"[{self.ip}] Polling DDM for ifIndex {if_index} using {ddm_index_type} {target_index}")
        tasks = {}
        mib_objects_to_get = {
            'rx_signal': self.symbolic_config.get('rx_power'), 'tx_signal': self.symbolic_config.get('tx_power'),
            'sfp_vendor': self.symbolic_config.get('sfp_vendor'), 'part_number': self.symbolic_config.get('part_num'),
            'serial_number': self.symbolic_config.get('serial_num'), 'temperature': self.symbolic_config.get('temperature'),
            'voltage': self.symbolic_config.get('voltage'),
        }
        for key, mib_obj_name in mib_objects_to_get.items():
            if mib_obj_name:
                symbol_parts = mib_obj_name.split('::')
                symbol = (symbol_parts[0], symbol_parts[1], target_index) if len(symbol_parts) == 2 else (mib_obj_name, target_index)
                tasks[key] = snmp_get_symbolic(self.snmp_engine, self.community, self.ip, self.port, *symbol)

        if not tasks: return port_result
        results = await asyncio.gather(*tasks.values())
        results_map = dict(zip(tasks.keys(), results))

        for key, mib_var_tuple in results_map.items():
            parsed_value = None
            if mib_var_tuple:
                oid_obj, value_obj = mib_var_tuple
                mib_object_name = mib_objects_to_get.get(key, '')
                # Критично: Особая обработка для стандартных сенсоров
                if ENTITY_SENSOR_VALUE in mib_object_name:
                    sensor_index = oid_obj[-1]
                    sensor_details = await self._get_sensor_details(sensor_index)
                    try:
                         raw_sensor_value = float(value_obj.prettyPrint())
                         scaled_value = raw_sensor_value * sensor_details['value_factor']
                         sensor_units = (sensor_details.get('units') or '').lower()
                         if 'watt' in sensor_units and key in ['rx_signal', 'tx_signal']:
                             parsed_value = mw_to_dbm(scaled_value * 1000) # W -> mW -> dBm
                         elif 'celsius' in sensor_units and key == 'temperature':
                             parsed_value = round(scaled_value, 2)
                         else: parsed_value = round(scaled_value, sensor_details.get('precision') or 2)
                    except Exception: parsed_value = None
                else:
                    parsed_value = parse_snmp_value(mib_var_tuple, self.switch_model)
            port_result[key] = parsed_value
            logger.debug(f"[{self.ip}] Index={target_index} - {key}: Parsed={parsed_value}")
        return port_result

    async def poll_and_update(self):
        logger.info(f"----- Starting MIB poll for {self.switch.hostname or self.ip} -----")
        if not await self._load_mibs_for_model():
             logger.warning(f"[{self.ip}] Failed to load MIBs for model. Poll may be incomplete.")
        if not self._load_symbolic_config():
             pass # Продолжаем без специфичных объектов

        if not await self._get_interfaces(): return # Нет интерфейсов - нет работы

        if self.symbolic_config.get('ddm_index_type') == 'entPhysicalIndex':
            await self._get_physical_entity_mapping() # Нужен маппинг

        port_poll_tasks = [self._poll_port_data(if_index) for if_index in self.interfaces.keys()]
        all_ports_data_list = await asyncio.gather(*port_poll_tasks, return_exceptions=True)

        updated_count, created_count = 0, 0
        now = timezone.now()
        try:
            # Критично: Атомарное обновление данных одного коммутатора
            async with transaction.atomic():
                for i, port_data_result in enumerate(all_ports_data_list):
                    if isinstance(port_data_result, Exception): logger.error(f"[{self.ip}] Port poll task failed: {port_data_result}"); continue
                    if not port_data_result or 'if_index' not in port_data_result: continue

                    if_index = port_data_result['if_index']
                    interface_info = self.interfaces.get(if_index, {})
                    defaults = {
                        'description': interface_info.get('description') or interface_info.get('ifDescr'),
                        'speed': interface_info.get('speed', 0), 'admin': interface_info.get('admin_status'),
                        'oper': interface_info.get('oper_status'), 'lastchange': interface_info.get('last_change', 0),
                        'name': interface_info.get('name') or f'Port {if_index}', 'alias': interface_info.get('alias', ''),
                        'data': now, 'rx_signal': port_data_result.get('rx_signal'), 'tx_signal': port_data_result.get('tx_signal'),
                        'sfp_vendor': port_data_result.get('sfp_vendor'), 'part_number': port_data_result.get('part_number'),
                        'serial_number': port_data_result.get('serial_number'),
                        # Добавить temperature/voltage если нужно
                    }
                    try:
                        obj, created = await SwitchesPorts.objects.aupdate_or_create(
                            switch=self.switch, port=if_index, defaults=defaults
                        )
                        if created: created_count += 1
                        else: updated_count += 1
                    except Exception as db_err:
                         logger.error(f"[{self.ip}] DB update/create failed for port {if_index}: {db_err}")
        except Exception as e:
             logger.error(f"[{self.ip}] DB transaction failed: {e}")

        if created_count > 0: logger.info(f"[{self.ip}] Created {created_count} SwitchesPorts.")
        if updated_count > 0: logger.info(f"[{self.ip}] Updated {updated_count} SwitchesPorts.")
        logger.info(f"----- Finished MIB poll for {self.switch.hostname or self.ip} -----")


class Command(BaseCommand):
    help = 'Update optical port DDM/DOM info using MIB symbolic names.'

    def add_arguments(self, parser):
        parser.add_argument('--switch-id', type=int, help='Poll only switch with this DB ID.')
        parser.add_argument('--ip', type=str, help='Poll only switch with this IP address.')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of switches (0=no limit).')
        parser.add_argument('--community', type=str, help='Override SNMP community string.')
        parser.add_argument('--timeout', type=int, default=5, help='SNMP timeout seconds.')
        parser.add_argument('--retries', type=int, default=1, help='SNMP retries.')
        parser.add_argument('--workers', type=int, default=10, help='Concurrent switch polling workers.')
        parser.add_argument('--run-once', action='store_true', help='Run once and exit.')
        parser.add_argument('--sleep', type=int, default=300, help='Sleep seconds between cycles.')

    async def handle_async(self, *args, **options):
        timeout, retries, max_workers = options['timeout'], options['retries'], options['workers']
        limit, override_community = options['limit'], options['community']

        switches_qs = Switch.objects.select_related('model', 'model__vendor').filter(status=True).order_by('?')
        if options['switch_id']: switches_qs = switches_qs.filter(pk=options['switch_id'])
        elif options['ip']: switches_qs = switches_qs.filter(ip=options['ip'])
        if limit > 0: switches_qs = switches_qs[:limit]

        switches_to_poll = [s async for s in switches_qs]
        if not switches_to_poll: self.stdout.write(self.style.WARNING('No active switches found to poll.')); return
        self.stdout.write(f"Starting poll cycle for {len(switches_to_poll)} switches...")

        tasks = []
        for switch in switches_to_poll:
             if not switch.ip: logger.warning(f"Switch '{switch.hostname or switch.id}' has no IP. Skipping."); continue
             if override_community: switch.snmp_community_ro = override_community
             poller = SNMPDevicePoller(switch, timeout=timeout, retries=retries)
             tasks.append(poller.poll_and_update())

        semaphore = asyncio.Semaphore(max_workers)
        async def run_with_semaphore(task):
            async with semaphore:
                try: await task
                except Exception as e: logger.error(f"Unhandled poll task exception: {e}", exc_info=True)

        await asyncio.gather(*(run_with_semaphore(task) for task in tasks))
        self.stdout.write(self.style.SUCCESS(f"Poll cycle finished for {len(switches_to_poll)} switches."))

    def handle(self, *args, **options):
        run_once, sleep_interval = options['run_once'], options['sleep']
        loop_func = self.handle_async

        async def main_loop():
            if run_once: await loop_func(*args, **options)
            else:
                self.stdout.write(self.style.WARNING(f"Continuous mode. Press Ctrl+C to stop."))
                while True:
                    start_time = time.time()
                    try: await loop_func(*args, **options)
                    except KeyboardInterrupt: self.stdout.write(self.style.ERROR("Interrupted by user.")); break
                    except Exception as e: logger.error(f"Critical error in main loop: {e}", exc_info=True)
                    elapsed, wait = time.time() - start_time, 0
                    wait = max(0, sleep_interval - elapsed)
                    self.stdout.write(f"Cycle took {elapsed:.2f}s. Sleeping for {wait:.2f}s...")
                    await asyncio.sleep(wait)
        try: asyncio.run(main_loop())
        except KeyboardInterrupt: self.stdout.write(self.style.ERROR("\nMain loop interrupted."))