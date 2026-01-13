import re
from typing import Optional, Tuple


_VIRTUAL_NAME_RE = re.compile(
    r"(loopback|lo\d*|vlan|vl\d+|bridge|br\d*|tunnel|tun\d*|ppp|mpls|l2vlan|l3vlan|virtual|cpu|null|stack|port-?channel|bond|lag|ae\d*|po\d*)",
    re.IGNORECASE,
)


def is_virtual_interface(
    if_type: Optional[int],
    if_name: Optional[str],
    if_descr: Optional[str],
    if_alias: Optional[str],
) -> Tuple[bool, str]:
    """Best-effort virtual interface detection.

    Returns: (is_virtual, reason)
    """
    name = (if_name or '')
    descr = (if_descr or '')
    alias = (if_alias or '')

    # Common virtual interface types (IANAifType values).
    # This list is intentionally conservative.
    virtual_ift_types = {
        24,  # softwareLoopback
        53,  # propVirtual
        131, # tunnel
        135, # l2vlan
        136, # l3vlan
        161, # ieee8023adLag
    }

    if if_type in virtual_ift_types:
        return True, f"ifType={if_type}"

    haystack = f"{name} {descr} {alias}".strip()
    if haystack and _VIRTUAL_NAME_RE.search(haystack):
        return True, "name/descr/alias matches virtual pattern"

    return False, ""
