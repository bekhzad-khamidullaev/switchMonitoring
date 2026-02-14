import re
from typing import Dict


VENDOR_PATTERNS = [
    ('eltex', re.compile(r'\b(MES|Eltex)\b', re.IGNORECASE)),
    ('huawei', re.compile(r'\b(Huawei|S33\d{2}|MA56\d+)\b', re.IGNORECASE)),
    ('zyxel', re.compile(r'\b(Zyxel|GS\d{4}|MGS\d{4})\b', re.IGNORECASE)),
    ('tp-link', re.compile(r'\b(TP-?LINK|T\d{4}G)\b', re.IGNORECASE)),
    ('snr', re.compile(r'\bSNR[-\w]+\b', re.IGNORECASE)),
]

MODEL_PATTERN = re.compile(r'\b([A-Z][A-Z0-9-]{3,})\b')
FIRMWARE_PATTERN = re.compile(r'(?i)(?:version|firmware)[:\s]+([\w.()-]+)')


def normalize_vendor_model(sys_object_id: str, sys_descr: str) -> Dict[str, str]:
    text = f"{sys_object_id} {sys_descr}".strip()

    vendor = 'unknown'
    for candidate, pattern in VENDOR_PATTERNS:
        if pattern.search(text):
            vendor = candidate
            break

    model = ''
    model_match = MODEL_PATTERN.search(sys_descr or '')
    if model_match:
        model = model_match.group(1)

    firmware = ''
    fw_match = FIRMWARE_PATTERN.search(sys_descr or '')
    if fw_match:
        firmware = fw_match.group(1)

    return {
        'vendor': vendor,
        'model': model,
        'firmware': firmware,
    }
