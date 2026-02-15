import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from snmp.models import DeviceProfile, MetricDefinition, MetricBinding

ROOT_OIDS = {
    'iso': '1',
    'org': '1.3',
    'dod': '1.3.6',
    'internet': '1.3.6.1',
    'mgmt': '1.3.6.1.2',
    'mib-2': '1.3.6.1.2.1',
    'enterprises': '1.3.6.1.4.1',
}

OBJECT_TYPE_RE = re.compile(
    r'(?ms)^\s*([A-Za-z][\w-]+)\s+(?:OBJECT-TYPE|OBJECT\s+IDENTIFIER)\b.*?::=\s*\{\s*([^{}]+)\s*\}'
)

METRIC_MAP = {
    'cpu_usage': re.compile(r'cpu.*(util|usage|load|percent)|processor.*(util|usage|load|percent)', re.I),
    'memory_usage': re.compile(r'mem.*(util|usage|load|percent|free|used)|buffer.*(util|usage|load|percent)', re.I),
    'device_temperature': re.compile(r'temp.*(value|sensor|level|celsius|celsius|deg)', re.I),
    'optical_rx_power': re.compile(r'(optical|rx|laser).*(power|level|signal|dbm)', re.I),
    'optical_tx_power': re.compile(r'(optical|tx|laser).*(power|level|signal|dbm)', re.I),
}

def _parse_assignment_rhs(rhs: str) -> Optional[Tuple[str, int]]:
    rhs_clean = ' '.join(rhs.strip().split())
    tokens = rhs_clean.split(' ')
    if not tokens: return None
    if all(t.isdigit() for t in tokens):
        dotted = '.'.join(tokens)
        return dotted, -1
    if len(tokens) >= 2 and tokens[-1].isdigit():
        parent = tokens[0]
        return parent, int(tokens[-1])
    return None

def _extract_symbols(text: str) -> Dict[str, Tuple[str, int]]:
    result: Dict[str, Tuple[str, int]] = {}
    for match in OBJECT_TYPE_RE.finditer(text):
        symbol = match.group(1)
        rhs = match.group(2)
        parsed = _parse_assignment_rhs(rhs)
        if parsed:
            result[symbol] = parsed
    return result

def _resolve_symbol_oid(symbol: str, raw_map: Dict[str, Tuple[str, int]], cache: Dict[str, str], seen: Set[str]) -> Optional[str]:
    if symbol in cache: return cache[symbol]
    if symbol in seen: return None
    seen.add(symbol)
    raw = raw_map.get(symbol)
    if raw is None: return None
    parent, suffix = raw
    if suffix == -1:
        cache[symbol] = parent
        return parent
    if parent in ROOT_OIDS:
        oid = f"{ROOT_OIDS[parent]}.{suffix}"
        cache[symbol] = oid
        return oid
    if re.match(r'^\d+(?:\.\d+)*$', parent):
        oid = f"{parent}.{suffix}"
        cache[symbol] = oid
        return oid
    parent_oid = _resolve_symbol_oid(parent, raw_map, cache, seen)
    if not parent_oid: return None
    oid = f"{parent_oid}.{suffix}"
    cache[symbol] = oid
    return oid

class Command(BaseCommand):
    help = 'Discover and create profiles and bindings by scanning the entire MIB database'

    def add_arguments(self, parser):
        parser.add_argument('--path', default='mibs', help='Path to MIB directory')
        parser.add_argument('--apply', action='store_true', help='Persist changes to DB')
        parser.add_argument('--vendor-filter', default='', help='Partial vendor name to filter')

    def handle(self, *args, **options):
        root = Path(options['path']).expanduser().resolve()
        apply = options['apply']
        vendor_filter = options['vendor_filter'].lower()

        if not root.exists():
            raise CommandError(f'Path {root} does not exist')

        self.stdout.write(f"Scanning {root}...")
        
        metric_objs = {m.key: m for m in MetricDefinition.objects.all()}
        skipped_dirs = {'standard', 'iana', 'ietf', 'archive', 'misc', 'mibs-with-errors', 'standard'}
        
        total_profiles = 0
        total_bindings = 0

        for vendor_dir in root.iterdir():
            if not vendor_dir.is_dir() or vendor_dir.name.lower() in skipped_dirs:
                continue
            
            vendor_name = vendor_dir.name.lower()
            if vendor_filter and vendor_filter not in vendor_name:
                continue

            self.stdout.write(f"Processing vendor: {vendor_name}...", ending='\r')
            
            raw_symbols = {}
            models = set()

            for mib_file in vendor_dir.rglob('*'):
                if not mib_file.is_file() or mib_file.suffix.lower() not in {'.mib', '.txt', '.my'}:
                    continue
                
                try:
                    text = mib_file.read_text(errors='ignore')
                    symbols = _extract_symbols(text)
                    raw_symbols.update(symbols)
                    
                    # Heuristic model name from filename
                    model_match = re.search(r'([A-Z0-9]{3,})', mib_file.stem)
                    if model_match:
                        models.add(model_match.group(1))
                except Exception:
                    pass

            if not raw_symbols:
                continue

            resolved = {}
            for symbol in raw_symbols:
                _resolve_symbol_oid(symbol, raw_symbols, resolved, set())

            vendor_metrics = {}
            for symbol, oid in resolved.items():
                for metric_key, pattern in METRIC_MAP.items():
                    if pattern.search(symbol):
                        vendor_metrics.setdefault(metric_key, []).append((symbol, oid))

            if not vendor_metrics:
                continue

            # Limit model pattern length
            pattern = "|".join(sorted(models)) if models else ".*"
            if len(pattern) > 200: pattern = ".*"

            if apply:
                with transaction.atomic():
                    profile, _ = DeviceProfile.objects.update_or_create(
                        vendor=vendor_name,
                        model_pattern=pattern,
                        defaults={'priority': 250, 'active': True}
                    )
                    total_profiles += 1
                    
                    for m_key, m_list in vendor_metrics.items():
                        if m_key not in metric_objs: continue
                        
                        symbol, oid = m_list[0]
                        strategy = MetricBinding.IndexStrategy.IF_INDEX if 'optical' in m_key or 'if' in symbol.lower() else MetricBinding.IndexStrategy.FIXED
                        
                        MetricBinding.objects.update_or_create(
                            profile=profile,
                            metric=metric_objs[m_key],
                            defaults={
                                'oid_template': oid,
                                'index_strategy': strategy,
                                'enabled_by_default': True
                            }
                        )
                        total_bindings += 1
            else:
                self.stdout.write(f"\nDry-run: Vendor {vendor_name} -> {len(vendor_metrics)} metrics found")

        self.stdout.write(f"\nDiscovery complete. Profiles: {total_profiles}, Bindings: {total_bindings}")
