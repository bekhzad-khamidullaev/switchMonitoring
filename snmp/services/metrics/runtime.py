import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from snmp.models import Device, Interface, MetricBinding

SENTINEL_INVALID_NUMBERS = {-65535.0, -32768.0, 2147483647.0}


@dataclass
class OidResolution:
    oid: str
    index: Optional[int]


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def mw_to_dbm(mw: float) -> Optional[float]:
    if mw <= 0:
        return None
    return 10 * math.log10(mw / 1000.0)


def apply_converter(converter: str, raw_value: Any, binding_params: Optional[Dict[str, Any]] = None) -> Any:
    params = binding_params or {}

    if converter == MetricBinding.Converter.IDENTITY:
        return raw_value

    numeric = _as_float(raw_value)
    if numeric is None and converter != MetricBinding.Converter.ENUM_MAP:
        return None

    if converter == MetricBinding.Converter.DIV10:
        return numeric / 10.0
    if converter == MetricBinding.Converter.DIV100:
        return numeric / 100.0
    if converter == MetricBinding.Converter.DIV1000:
        return numeric / 1000.0
    if converter == MetricBinding.Converter.MW_TO_DBM:
        return mw_to_dbm(numeric)
    if converter == MetricBinding.Converter.ENUM_MAP:
        enum_map = params.get('enum_map', {})
        return enum_map.get(str(raw_value), enum_map.get(raw_value, raw_value))

    return raw_value


def is_invalid_numeric(value: Any, binding_params: Optional[Dict[str, Any]] = None) -> bool:
    params = binding_params or {}
    numeric = _as_float(value)
    if numeric is None:
        return False

    invalid_values = {_as_float(v) for v in params.get('invalid_values', [])}
    invalid_values = {v for v in invalid_values if v is not None}
    all_invalid = SENTINEL_INVALID_NUMBERS | invalid_values
    if numeric in all_invalid:
        return True

    min_allowed = _as_float(params.get('min_allowed'))
    max_allowed = _as_float(params.get('max_allowed'))
    if min_allowed is not None and numeric < min_allowed:
        return True
    if max_allowed is not None and numeric > max_allowed:
        return True

    return False


def validate_numeric(value: Any, binding_params: Optional[Dict[str, Any]] = None) -> Optional[float]:
    numeric = _as_float(value)
    if numeric is None:
        return None

    if is_invalid_numeric(numeric, binding_params):
        return None

    return numeric


def render_oid(binding: MetricBinding, device: Device, interface: Optional[Interface] = None) -> OidResolution:
    params = binding.binding_params or {}
    index = None

    if binding.index_strategy == MetricBinding.IndexStrategy.IF_INDEX:
        if interface is None:
            raise ValueError('Interface is required for if_index strategy')
        index = interface.if_index
    elif binding.index_strategy == MetricBinding.IndexStrategy.FIXED:
        index = params.get('fixed_index')
        if index is None:
            raise ValueError('fixed_index is required in binding_params for fixed strategy')
    elif binding.index_strategy == MetricBinding.IndexStrategy.VENDOR_MAP:
        vendor_map = params.get('vendor_map', {})
        index = vendor_map.get(device.vendor, params.get('default_index'))
        if index is None:
            raise ValueError('vendor_map/default_index is required for vendor_map strategy')

    try:
        index = int(index) if index is not None else None
    except (TypeError, ValueError) as exc:
        raise ValueError('Index should be an integer') from exc

    format_args = {
        'if_index': interface.if_index if interface else '',
        'index': index if index is not None else '',
        'device_ip': device.ip,
        'vendor': device.vendor,
        'model': device.model,
    }
    oid = binding.oid_template.format(**format_args)
    return OidResolution(oid=oid, index=index)


def build_binding_oid_requests(
    device: Device,
    bindings: Iterable[MetricBinding],
    interface: Optional[Interface] = None,
) -> Dict[int, OidResolution]:
    requests: Dict[int, OidResolution] = {}
    for binding in bindings:
        requests[binding.id] = render_oid(binding=binding, device=device, interface=interface)
    return requests
