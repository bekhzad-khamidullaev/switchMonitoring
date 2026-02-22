import re
from typing import Dict


ENTERPRISE_VENDOR_MAP = {
    "9": "cisco",
    "11": "hp",
    "171": "d-link",
    "674": "dell",
    "890": "extreme",
    "2011": "huawei",
    "2636": "juniper",
    "3320": "dell",
    "4526": "netgear",
    "6486": "alcatel",
    "14988": "mikrotik",
    "11863": "zyxel",
    "12356": "fortinet",
    "25506": "h3c",
    "25461": "ubnt",
    "3224": "allied",
}

VENDOR_PATTERNS = [
    ("iskratel", re.compile(r"\b(Iskratel|SI3\d{2,3}|SI2\d{2,3}|Innbox|MSAN|ESCOM)\b", re.IGNORECASE)),
    ("cisco", re.compile(r"\b(Cisco|Catalyst|Nexus|IOS XE|IOS XR)\b", re.IGNORECASE)),
    ("juniper", re.compile(r"\b(Juniper|JUNOS|EX\d+|MX\d+|QFX\d+|SRX\d+)\b", re.IGNORECASE)),
    ("mikrotik", re.compile(r"\b(MikroTik|RouterOS|RB\d+|CCR\d+|CRS\d+)\b", re.IGNORECASE)),
    ("fortinet", re.compile(r"\b(Fortinet|FortiGate)\b", re.IGNORECASE)),
    ("ubnt", re.compile(r"\b(Ubiquiti|UniFi|EdgeRouter|EdgeSwitch)\b", re.IGNORECASE)),
    ("d-link", re.compile(r"\b(D-?Link|DGS[-\w]*|DES[-\w]*)\b", re.IGNORECASE)),
    ("zyxel", re.compile(r"\b(Zyxel|GS\d{3,4}|XGS\d{3,4}|MGS\d{3,4})\b", re.IGNORECASE)),
    ("h3c", re.compile(r"\b(H3C|Comware)\b", re.IGNORECASE)),
    ('eltex', re.compile(r'\b(MES|Eltex)\b', re.IGNORECASE)),
    ('huawei', re.compile(r'\b(Huawei|S33\d{2}|MA56\d+)\b', re.IGNORECASE)),
    ('tp-link', re.compile(r'\b(TP-?LINK|T\d{4}G|TL-SG\d+)\b', re.IGNORECASE)),
    ('snr', re.compile(r'\bSNR[-\w]+\b', re.IGNORECASE)),
]

MODEL_HINT_PATTERNS = [
    re.compile(r'(?i)\b(?:model|platform|device)\s*[:=]\s*([A-Za-z0-9][A-Za-z0-9._-]{2,})'),
    re.compile(r'\b((?:Catalyst|Nexus|ISR|ASR|EdgeRouter|EdgeSwitch|UniFi)[A-Za-z0-9-]*)\b', re.IGNORECASE),
    re.compile(r'\b([A-Z]{1,5}\d{2,}[A-Z0-9-]{0,})\b'),
]
FIRMWARE_PATTERN = re.compile(r'(?i)(?:version|firmware)[:\s]+([\w.()-]+)')
ENTERPRISE_OID_PATTERN = re.compile(r'1\.3\.6\.1\.4\.1\.(\d+)')


def _vendor_from_sys_object_id(sys_object_id: str) -> str:
    match = ENTERPRISE_OID_PATTERN.search(sys_object_id or '')
    if not match:
        return ''
    return ENTERPRISE_VENDOR_MAP.get(match.group(1), '')


def _extract_model(sys_descr: str) -> str:
    text = (sys_descr or '').strip()
    if not text:
        return ''

    for pattern in MODEL_HINT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        candidate = (match.group(1) or '').strip()
        if not candidate:
            continue
        upper_candidate = candidate.upper()
        if upper_candidate in {'VERSION', 'FIRMWARE', 'RELEASE', 'BUILD', 'SOFTWARE'}:
            continue
        if candidate.isdigit():
            continue
        return candidate
    return ''


def normalize_vendor_model(sys_object_id: str, sys_descr: str) -> Dict[str, str]:
    text = f"{sys_object_id} {sys_descr}".strip()

    vendor = _vendor_from_sys_object_id(sys_object_id) or 'unknown'
    if vendor == 'unknown':
        for candidate, pattern in VENDOR_PATTERNS:
            if pattern.search(text):
                vendor = candidate
                break

    model = _extract_model(sys_descr)

    firmware = ''
    fw_match = FIRMWARE_PATTERN.search(sys_descr or '')
    if fw_match:
        firmware = fw_match.group(1)

    return {
        'vendor': vendor,
        'model': model,
        'firmware': firmware,
    }
