from __future__ import annotations

from snmp.models import Interface

GPON_TOKENS = ("gpon", "xgpon", "epon", "pon")
ETHERNET_TOKENS = ("ethernet", "eth", "ge", "xe", "te", "gi", "fa")
OPTICAL_TOKENS = ("sfp", "qsfp", "xfp", "optic", "fiber", "fibre")


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def is_gpon(interface: Interface) -> bool:
    text = " ".join((_norm(interface.if_name), _norm(interface.if_alias), _norm(interface.if_type)))
    return any(token in text for token in GPON_TOKENS)


def is_ethernet(interface: Interface) -> bool:
    if _norm(interface.if_type) in {"6", "ethernetcsmacd"}:
        return True

    text = " ".join((_norm(interface.if_name), _norm(interface.if_alias), _norm(interface.if_type)))
    return any(token in text for token in ETHERNET_TOKENS)


def is_optical(interface: Interface) -> bool:
    if interface.is_optical:
        return True
    text = " ".join((_norm(interface.if_name), _norm(interface.if_alias), _norm(interface.if_type)))
    return any(token in text for token in OPTICAL_TOKENS)


def is_eligible_optical_ethernet(interface: Interface) -> bool:
    return is_ethernet(interface) and is_optical(interface) and not is_gpon(interface)
