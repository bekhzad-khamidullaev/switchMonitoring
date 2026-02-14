import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from snmp.models import MetricDefinition

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
    r'(?ms)^\s*([A-Za-z][\w-]+)\s+OBJECT-TYPE\b.*?::=\s*\{\s*([^{}]+)\s*\}'
)
OBJECT_ID_RE = re.compile(
    r'(?ms)^\s*([A-Za-z][\w-]+)\s+OBJECT\s+IDENTIFIER\s*::=\s*\{\s*([^{}]+)\s*\}'
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _iter_mib_files(root: Path) -> Iterable[Path]:
    for path in root.rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.mib', '.txt', '.my'}:
            yield path


def _parse_assignment_rhs(rhs: str) -> Optional[Tuple[str, int]]:
    rhs_clean = ' '.join(rhs.strip().split())
    tokens = rhs_clean.split(' ')
    if not tokens:
        return None

    if all(t.isdigit() for t in tokens):
        dotted = '.'.join(tokens)
        return dotted, -1

    if len(tokens) >= 2 and tokens[-1].isdigit():
        parent = tokens[0]
        return parent, int(tokens[-1])

    return None


def _extract_symbols(text: str) -> Dict[str, Tuple[str, int]]:
    result: Dict[str, Tuple[str, int]] = {}

    for regex in (OBJECT_ID_RE, OBJECT_TYPE_RE):
        for match in regex.finditer(text):
            symbol = match.group(1)
            rhs = match.group(2)
            parsed = _parse_assignment_rhs(rhs)
            if parsed:
                result[symbol] = parsed

    return result


def _resolve_symbol_oid(symbol: str, raw_map: Dict[str, Tuple[str, int]], cache: Dict[str, str], seen: Set[str]) -> Optional[str]:
    if symbol in cache:
        return cache[symbol]
    if symbol in seen:
        return None

    seen.add(symbol)
    raw = raw_map.get(symbol)
    if raw is None:
        return None

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
    if not parent_oid:
        return None

    oid = f"{parent_oid}.{suffix}"
    cache[symbol] = oid
    return oid


def _resolve_oids(raw_map: Dict[str, Tuple[str, int]]) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    for symbol in raw_map.keys():
        _resolve_symbol_oid(symbol, raw_map, resolved, set())
    return resolved


def _normalize_metric_key(symbol: str) -> str:
    key = symbol.strip().lower().replace('-', '_')
    return re.sub(r'[^a-z0-9_]+', '_', key)


class Command(BaseCommand):
    help = 'Import MIB symbols and OIDs into metric catalog (MetricDefinition)'

    def add_arguments(self, parser):
        parser.add_argument('--path', required=True, help='Path to MIB directory')
        parser.add_argument('--dry-run', action='store_true', help='Analyze only without DB writes')
        parser.add_argument('--apply', action='store_true', help='Persist MetricDefinition changes')
        parser.add_argument(
            '--cache-file',
            default=str(settings.BASE_DIR / '.cache' / 'mib_import_cache.json'),
            help='Path to parse cache json file',
        )
        parser.add_argument(
            '--conflicts-out',
            default=str(settings.BASE_DIR / 'docs' / 'mib_symbol_conflicts.json'),
            help='Where to write conflicts report',
        )
        parser.add_argument(
            '--conflict-resolution',
            default='',
            help='Optional JSON file with manual symbol->oid resolution for conflicts',
        )

    def handle(self, *args, **options):
        root = Path(options['path']).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise CommandError(f'Invalid --path: {root}')

        dry_run = options['dry_run'] or not options['apply']
        cache_file = Path(options['cache_file']).expanduser().resolve()
        conflicts_out = Path(options['conflicts_out']).expanduser().resolve()
        conflict_resolution_path = options.get('conflict_resolution') or ''

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        conflicts_out.parent.mkdir(parents=True, exist_ok=True)

        if cache_file.exists():
            cache = json.loads(cache_file.read_text())
        else:
            cache = {'version': 1, 'files': {}}

        file_cache = cache.get('files', {})

        merged: Dict[str, Set[str]] = {}
        scanned = 0
        reused_from_cache = 0

        for file_path in _iter_mib_files(root):
            scanned += 1
            content = file_path.read_bytes()
            digest = _sha256(content)
            key = str(file_path)

            cached = file_cache.get(key)
            if cached and cached.get('sha256') == digest:
                resolved = cached.get('resolved', {})
                reused_from_cache += 1
            else:
                text = content.decode('utf-8', errors='ignore')
                raw_symbols = _extract_symbols(text)
                resolved = _resolve_oids(raw_symbols)
                file_cache[key] = {
                    'sha256': digest,
                    'resolved': resolved,
                }

            for symbol, oid in resolved.items():
                merged.setdefault(symbol, set()).add(oid)

        cache['files'] = file_cache
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

        conflicts = {symbol: sorted(list(oids)) for symbol, oids in merged.items() if len(oids) > 1}
        conflicts_out.write_text(json.dumps(conflicts, ensure_ascii=False, indent=2))

        resolution_map = {}
        if conflict_resolution_path:
            resolution_file = Path(conflict_resolution_path).expanduser().resolve()
            if resolution_file.exists():
                resolution_map = json.loads(resolution_file.read_text())

        unique_symbols = {symbol: next(iter(oids)) for symbol, oids in merged.items() if len(oids) == 1}
        resolved_conflicts = 0
        for symbol, oid_choices in conflicts.items():
            chosen = resolution_map.get(symbol)
            if chosen and chosen in oid_choices:
                unique_symbols[symbol] = chosen
                resolved_conflicts += 1

        create_count = 0
        update_count = 0
        skipped_conflicts = len(conflicts)

        existing_by_key = {}
        if not dry_run:
            existing_by_key = {
                row['key']: row['id']
                for row in MetricDefinition.objects.values('id', 'key')
            }

        for symbol, oid in unique_symbols.items():
            key = _normalize_metric_key(symbol)
            if key in existing_by_key:
                continue

            create_count += 1
            if not dry_run:
                MetricDefinition.objects.create(
                    key=key,
                    title=symbol,
                    description=f'Imported from MIB symbol {symbol} ({oid})',
                    unit='',
                    value_type=MetricDefinition.ValueType.FLOAT,
                    default_interval_sec=300,
                )

        self.stdout.write(self.style.SUCCESS('MIB import analysis complete'))
        self.stdout.write(f'  files_scanned={scanned}')
        self.stdout.write(f'  cache_reused={reused_from_cache}')
        self.stdout.write(f'  symbols_total={len(merged)}')
        self.stdout.write(f'  symbols_conflicts={skipped_conflicts}')
        self.stdout.write(f'  symbols_conflicts_resolved={resolved_conflicts}')
        self.stdout.write(f'  metric_definitions_new={create_count}')
        self.stdout.write(f'  dry_run={dry_run}')
        self.stdout.write(f'  conflicts_report={conflicts_out}')
