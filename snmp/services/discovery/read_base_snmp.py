import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

OID_SYS_OBJECT_ID = '1.3.6.1.2.1.1.2.0'
OID_SYS_DESCR = '1.3.6.1.2.1.1.1.0'
OID_IF_INDEX = '1.3.6.1.2.1.2.2.1.1'
OID_IF_DESCR = '1.3.6.1.2.1.2.2.1.2'
OID_IF_TYPE = '1.3.6.1.2.1.2.2.1.3'
OID_IF_ALIAS = '1.3.6.1.2.1.31.1.1.1.18'
OID_IF_ADMIN_STATUS = '1.3.6.1.2.1.2.2.1.7'
OID_IF_OPER_STATUS = '1.3.6.1.2.1.2.2.1.8'


class SnmpReadError(RuntimeError):
    pass


def _import_pysnmp():
    try:
        from pysnmp.hlapi import (
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            getCmd,
            nextCmd,
        )
    except ModuleNotFoundError as exc:
        raise SnmpReadError('pysnmp is not installed in this environment') from exc
    return {
        'CommunityData': CommunityData,
        'ContextData': ContextData,
        'ObjectIdentity': ObjectIdentity,
        'ObjectType': ObjectType,
        'SnmpEngine': SnmpEngine,
        'UdpTransportTarget': UdpTransportTarget,
        'getCmd': getCmd,
        'nextCmd': nextCmd,
    }


def snmp_get(ip: str, community: str, oid: str, timeout: int = 2, retries: int = 1) -> str:
    api = _import_pysnmp()
    iterator = api['getCmd'](
        api['SnmpEngine'](),
        api['CommunityData'](community),
        api['UdpTransportTarget']((ip, 161), timeout=timeout, retries=retries),
        api['ContextData'](),
        api['ObjectType'](api['ObjectIdentity'](oid)),
    )

    error_indication, error_status, _, var_binds = next(iterator)
    if error_indication:
        raise SnmpReadError(str(error_indication))
    if error_status:
        raise SnmpReadError(str(error_status.prettyPrint()))

    if not var_binds:
        return ''
    return str(var_binds[0][1]).strip()


def snmp_get_many(
    ip: str,
    community: str,
    oids: List[str],
    timeout: int = 2,
    retries: int = 1,
    batch_size: int = 20,
) -> Dict[str, Any]:
    api = _import_pysnmp()
    result: Dict[str, Any] = {}
    unique_oids = list(dict.fromkeys([oid for oid in oids if oid]))

    for offset in range(0, len(unique_oids), batch_size):
        chunk = unique_oids[offset : offset + batch_size]
        iterator = api['getCmd'](
            api['SnmpEngine'](),
            api['CommunityData'](community),
            api['UdpTransportTarget']((ip, 161), timeout=timeout, retries=retries),
            api['ContextData'](),
            *[api['ObjectType'](api['ObjectIdentity'](oid)) for oid in chunk],
        )

        try:
            error_indication, error_status, _, var_binds = next(iterator)
        except StopIteration:
            for oid in chunk:
                result[oid] = SnmpReadError('empty SNMP response')
            continue

        if error_indication:
            error = SnmpReadError(str(error_indication))
            for oid in chunk:
                result[oid] = error
            continue

        if error_status:
            error = SnmpReadError(str(error_status.prettyPrint()))
            for oid in chunk:
                result[oid] = error
            continue

        for oid, var_bind in zip(chunk, var_binds):
            result[oid] = str(var_bind[1]).strip()

        if len(var_binds) < len(chunk):
            for oid in chunk[len(var_binds) :]:
                result[oid] = ''

    return result


def snmp_walk_map(ip: str, community: str, oid: str, timeout: int = 2, retries: int = 1) -> Dict[int, str]:
    api = _import_pysnmp()
    output: Dict[int, str] = {}

    walker = api['nextCmd'](
        api['SnmpEngine'](),
        api['CommunityData'](community),
        api['UdpTransportTarget']((ip, 161), timeout=timeout, retries=retries),
        api['ContextData'](),
        api['ObjectType'](api['ObjectIdentity'](oid)),
        lexicographicMode=False,
    )

    for error_indication, error_status, _, var_binds in walker:
        if error_indication:
            raise SnmpReadError(str(error_indication))
        if error_status:
            raise SnmpReadError(str(error_status.prettyPrint()))

        if not var_binds:
            continue
        name, value = var_binds[0]
        oid_str = str(name)
        try:
            if_index = int(oid_str.split('.')[-1])
        except ValueError:
            continue
        output[if_index] = str(value).strip()

    return output


def read_base_snmp(ip: str, community: str, timeout: int = 2, retries: int = 1) -> Dict[str, Any]:
    sys_object_id = snmp_get(ip, community, OID_SYS_OBJECT_ID, timeout=timeout, retries=retries)
    sys_descr = snmp_get(ip, community, OID_SYS_DESCR, timeout=timeout, retries=retries)

    if_descr_map = snmp_walk_map(ip, community, OID_IF_DESCR, timeout=timeout, retries=retries)
    if_alias_map = snmp_walk_map(ip, community, OID_IF_ALIAS, timeout=timeout, retries=retries)
    if_type_map = snmp_walk_map(ip, community, OID_IF_TYPE, timeout=timeout, retries=retries)
    if_admin_map = snmp_walk_map(ip, community, OID_IF_ADMIN_STATUS, timeout=timeout, retries=retries)
    if_oper_map = snmp_walk_map(ip, community, OID_IF_OPER_STATUS, timeout=timeout, retries=retries)

    interfaces: List[Dict[str, Any]] = []
    for if_index, if_name in if_descr_map.items():
        if_type = if_type_map.get(if_index, '')
        is_optical = str(if_type) in {'117'} or 'sfp' in if_name.lower() or 'pon' in if_name.lower()
        interfaces.append(
            {
                'if_index': if_index,
                'if_name': if_name,
                'if_alias': if_alias_map.get(if_index, ''),
                'if_type': str(if_type),
                'is_optical': is_optical,
                'admin_up': if_admin_map.get(if_index) == '1',
                'oper_up': if_oper_map.get(if_index) == '1',
            }
        )

    logger.info('read_base_snmp completed', extra={'ip': ip, 'interfaces': len(interfaces)})
    return {
        'sys_object_id': sys_object_id,
        'sys_descr': sys_descr,
        'interfaces': interfaces,
    }
