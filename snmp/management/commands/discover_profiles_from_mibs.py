import re
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from snmp.models import DeviceProfile, MetricBinding, MetricDefinition

ROOT_OIDS = {
    "iso": "1",
    "org": "1.3",
    "dod": "1.3.6",
    "internet": "1.3.6.1",
    "mgmt": "1.3.6.1.2",
    "mib-2": "1.3.6.1.2.1",
    "enterprises": "1.3.6.1.4.1",
}

OBJECT_ASSIGNMENT_RE = re.compile(
    r"(?ms)^\s*([A-Za-z][\w-]+)\s+(?:OBJECT-TYPE|OBJECT\s+IDENTIFIER)\b.*?::=\s*\{\s*([^{}]+)\s*\}"
)
OBJECT_TYPE_SYNTAX_RE = re.compile(
    r"(?ms)^\s*([A-Za-z][\w-]+)\s+OBJECT-TYPE\b.*?SYNTAX\s+([^\r\n]+).*?::=\s*\{\s*([^{}]+)\s*\}"
)
MODEL_FROM_FILENAME_RE = re.compile(r"([A-Z]{2,}\d+[A-Z0-9-]*)")
NON_METRIC_SYMBOL_RE = re.compile(
    r"(table|entry|group|compliance|conformance|capability|capabilities|notification|notifications|objects|module)$",
    re.IGNORECASE,
)


def _parse_assignment_rhs(rhs: str) -> Optional[Tuple[str, int]]:
    rhs_clean = " ".join(rhs.strip().split())
    tokens = rhs_clean.split(" ")
    if not tokens:
        return None
    if all(token.isdigit() for token in tokens):
        return ".".join(tokens), -1
    if len(tokens) >= 2 and tokens[-1].isdigit():
        return tokens[0], int(tokens[-1])
    return None


def _extract_symbols(text: str) -> Dict[str, Tuple[str, int]]:
    result: Dict[str, Tuple[str, int]] = {}
    for match in OBJECT_ASSIGNMENT_RE.finditer(text):
        symbol = match.group(1)
        parsed = _parse_assignment_rhs(match.group(2))
        if parsed:
            result[symbol] = parsed
    return result


def _extract_syntax_map(text: str) -> Dict[str, str]:
    syntax_map: Dict[str, str] = {}
    for match in OBJECT_TYPE_SYNTAX_RE.finditer(text):
        syntax_map[match.group(1)] = " ".join((match.group(2) or "").split())
    return syntax_map


def _resolve_symbol_oid(
    symbol: str,
    raw_map: Dict[str, Tuple[str, int]],
    cache: Dict[str, str],
    seen: Set[str],
) -> Optional[str]:
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
    if re.match(r"^\d+(?:\.\d+)*$", parent):
        oid = f"{parent}.{suffix}"
        cache[symbol] = oid
        return oid

    parent_oid = _resolve_symbol_oid(parent, raw_map, cache, seen)
    if not parent_oid:
        return None
    oid = f"{parent_oid}.{suffix}"
    cache[symbol] = oid
    return oid


def _infer_metric_value_type(syntax: str) -> str:
    lowered = (syntax or "").lower()
    if "truthvalue" in lowered or "boolean" in lowered:
        return MetricDefinition.ValueType.BOOLEAN
    if any(token in lowered for token in ("counter", "gauge", "integer", "unsigned", "timeticks")):
        return MetricDefinition.ValueType.INTEGER
    return MetricDefinition.ValueType.TEXT


def _infer_unit(symbol: str, syntax: str) -> str:
    text = f"{symbol} {syntax}".lower()
    if "dbm" in text:
        return "dBm"
    if "percent" in text or "%" in text:
        return "%"
    if "celsius" in text or "temp" in text:
        return "C"
    if "timeticks" in text:
        return "timeticks"
    return ""


def _metric_key(vendor: str, symbol: str) -> str:
    normalized_vendor = re.sub(r"[^a-z0-9]+", "_", vendor.lower()).strip("_")
    normalized_symbol = re.sub(r"[^a-z0-9]+", "_", symbol.lower()).strip("_")
    if not normalized_symbol:
        normalized_symbol = "metric"
    base = f"{normalized_vendor}_{normalized_symbol}"
    if len(base) <= 80:
        return base
    checksum = str(abs(hash(base)) % 10000000)
    trimmed = base[: 80 - len(checksum) - 1].rstrip("_")
    return f"{trimmed}_{checksum}"


def _binding_payload(oid: str) -> tuple[str, str, dict]:
    if oid.endswith(".0"):
        return (
            f"{oid[:-2]}.{{index}}",
            MetricBinding.IndexStrategy.FIXED,
            {"fixed_index": 0},
        )
    return (
        f"{oid}.{{if_index}}",
        MetricBinding.IndexStrategy.IF_INDEX,
        {},
    )


class Command(BaseCommand):
    help = "Rebuild device profiles and metric bindings by scanning MIB files"

    def add_arguments(self, parser):
        parser.add_argument("--path", default="mibs", help="Path to MIB directory")
        parser.add_argument("--vendor-filter", default="", help="Partial vendor name to filter")
        parser.add_argument("--apply", action="store_true", help="Persist discovered profiles/metrics")
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Delete existing device profiles before import (bindings are deleted via cascade)",
        )

    def handle(self, *args, **options):
        root = Path(options["path"]).expanduser().resolve()
        vendor_filter = (options["vendor_filter"] or "").strip().lower()
        apply_changes = bool(options["apply"])
        rebuild = bool(options["rebuild"])

        if not root.exists():
            raise CommandError(f"Path {root} does not exist")
        if rebuild and not apply_changes:
            raise CommandError("--rebuild requires --apply")

        skipped_dirs = {"standard", "iana", "ietf", "archive", "misc", "mibs-with-errors"}
        vendor_dirs = [
            item for item in root.iterdir()
            if item.is_dir() and item.name.lower() not in skipped_dirs
        ]
        if vendor_filter:
            vendor_dirs = [item for item in vendor_dirs if vendor_filter in item.name.lower()]

        if apply_changes and rebuild:
            deleted_profiles, _ = DeviceProfile.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted profiles: {deleted_profiles}"))

        total_profiles = 0
        total_metrics = 0
        total_bindings = 0

        for vendor_dir in vendor_dirs:
            vendor = vendor_dir.name.lower()
            raw_symbols: Dict[str, Tuple[str, int]] = {}
            syntax_map: Dict[str, str] = {}
            model_tokens: Set[str] = set()

            for mib_file in vendor_dir.rglob("*"):
                if not mib_file.is_file() or mib_file.suffix.lower() not in {".mib", ".txt", ".my"}:
                    continue
                try:
                    text = mib_file.read_text(errors="ignore")
                except Exception:
                    continue

                raw_symbols.update(_extract_symbols(text))
                syntax_map.update(_extract_syntax_map(text))
                for model_match in MODEL_FROM_FILENAME_RE.findall(mib_file.stem):
                    model_tokens.add(model_match)

            if not raw_symbols or not syntax_map:
                continue

            resolved: Dict[str, str] = {}
            for symbol in raw_symbols:
                _resolve_symbol_oid(symbol, raw_symbols, resolved, set())

            metric_candidates = []
            for symbol, syntax in syntax_map.items():
                if NON_METRIC_SYMBOL_RE.search(symbol):
                    continue
                oid = resolved.get(symbol)
                if not oid or not re.match(r"^\d+(?:\.\d+)+$", oid):
                    continue
                metric_candidates.append((symbol, syntax, oid))

            if not metric_candidates:
                continue

            model_pattern = "|".join(sorted(model_tokens)) if model_tokens else ".*"
            if len(model_pattern) > 220:
                model_pattern = ".*"

            if not apply_changes:
                self.stdout.write(
                    f"Dry-run: vendor={vendor} metrics={len(metric_candidates)} model_pattern_len={len(model_pattern)}"
                )
                continue

            with transaction.atomic():
                profile, _ = DeviceProfile.objects.update_or_create(
                    vendor=vendor,
                    model_pattern=model_pattern,
                    firmware_pattern="",
                    defaults={"priority": 250, "active": True},
                )
                total_profiles += 1

                for symbol, syntax, oid in metric_candidates:
                    key = _metric_key(vendor, symbol)
                    title = symbol.replace("_", " ").replace("-", " ").strip().title()
                    value_type = _infer_metric_value_type(syntax)
                    unit = _infer_unit(symbol, syntax)
                    metric, created = MetricDefinition.objects.update_or_create(
                        key=key,
                        defaults={
                            "title": title or key,
                            "description": f"{vendor}::{symbol} ({syntax})",
                            "unit": unit,
                            "value_type": value_type,
                            "default_interval_sec": 300,
                        },
                    )
                    if created:
                        total_metrics += 1

                    oid_template, index_strategy, binding_params = _binding_payload(oid)
                    _, created_binding = MetricBinding.objects.update_or_create(
                        profile=profile,
                        metric=metric,
                        oid_template=oid_template,
                        index_strategy=index_strategy,
                        defaults={
                            "converter": MetricBinding.Converter.IDENTITY,
                            "binding_params": binding_params,
                            "scale": 1.0,
                            "enabled_by_default": True,
                            "priority": 250,
                        },
                    )
                    if created_binding:
                        total_bindings += 1

            self.stdout.write(
                f"Imported vendor={vendor} metrics={len(metric_candidates)} profile_id={profile.id}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Profiles upserted={total_profiles}, new metrics={total_metrics}, new bindings={total_bindings}"
            )
        )
