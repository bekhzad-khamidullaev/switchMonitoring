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


def _specificity(profile: DeviceProfile) -> int:
    score = 0
    if profile.vendor:
        score += 1
    if profile.model_pattern and profile.model_pattern != '.*':
        score += 1
    if profile.firmware_pattern and profile.firmware_pattern != '.*':
        score += 1
    return score


def match_device_profile(vendor: str, model: str, firmware: str) -> Optional[DeviceProfile]:
    candidates = DeviceProfile.objects.filter(active=True)
    matched = []

    for profile in candidates:
        if profile.vendor and profile.vendor.lower() != (vendor or '').lower():
            continue
        if not _matches(profile.model_pattern, model):
            continue
        if not _matches(profile.firmware_pattern, firmware):
            continue
        matched.append(profile)

    if not matched:
        return None

    # Deterministic rule: lowest priority first, then most specific rule.
    matched.sort(key=lambda p: (p.priority, -_specificity(p), p.id))
    return matched[0]
