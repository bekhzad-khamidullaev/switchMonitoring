import re
from typing import Optional

from snmp.models import DeviceProfile


def _matches(pattern: str, value: str) -> bool:
    if not pattern:
        return True
    # If pattern is .*, it should match empty value too (fallback case)
    if not value:
        return pattern == '.*' or pattern == ''
    return re.search(pattern, value, re.IGNORECASE) is not None


def match_device_profile(vendor: str, model: str, firmware: str) -> Optional[DeviceProfile]:
    candidates = DeviceProfile.objects.filter(active=True).order_by('priority', 'id')

    for profile in candidates:
        if profile.vendor and profile.vendor.lower() != (vendor or '').lower():
            continue
        if not _matches(profile.model_pattern, model):
            continue
        if not _matches(profile.firmware_pattern, firmware):
            continue
        return profile

    return None
