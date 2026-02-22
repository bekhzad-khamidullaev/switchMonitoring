import logging
from ipaddress import IPv4Network

from django.conf import settings
from django.core.management.base import BaseCommand

from snmp.models import Ats, Device
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.services.discovery.read_base_snmp import SnmpReadError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP DISCOVERY")


class Command(BaseCommand):
    help = "Auto-provision hosts from configured subnets and run SNMP discovery/profile auto-assignment"

    def add_arguments(self, parser):
        parser.add_argument("--community", default=settings.SNMP_DEFAULT_COMMUNITY_RO)
        parser.add_argument("--timeout", type=int, default=2)
        parser.add_argument("--retries", type=int, default=1)
        parser.add_argument("--dry-run", action="store_true", help="Only scan and report, do not write to DB")

    def check_host_reachability(self, ip):
        try:
            import nmap

            nm = nmap.PortScanner()
            nm_args = f"-sn {ip}"
            nm.scan(hosts=ip, arguments=nm_args)
            return nm[ip].state() == "up"
        except Exception as e:
            logger.error(f"Error while checking host {ip} reachability: {e}")
            return False

    def handle_subnet(self, subnet, ats, *, community, timeout, retries, dry_run):
        hosts = [str(host) for host in subnet.hosts()]
        summary = {"created": 0, "updated": 0, "discovered": 0, "failed": 0, "unreachable": 0}
        for ip_address in hosts:
            is_reachable = self.check_host_reachability(ip_address)
            if not is_reachable:
                summary["unreachable"] += 1
                logger.warning(f"Host {ip_address} is not reachable.")
                continue

            if dry_run:
                summary["updated"] += 1
                continue

            defaults = {
                "snmp_community_ro": settings.SNMP_DEFAULT_COMMUNITY_RO,
                "snmp_community_rw": settings.SNMP_DEFAULT_COMMUNITY_RW,
                "subgroup": ats,
                "group": ats.group,
            }
            device, created = Device.objects.get_or_create(ip=ip_address, defaults=defaults)
            if created:
                summary["created"] += 1
            else:
                updates = {}
                if not device.subgroup_id:
                    updates["subgroup"] = ats
                if not device.group_id and ats.group_id:
                    updates["group"] = ats.group
                if not device.snmp_community_ro:
                    updates["snmp_community_ro"] = settings.SNMP_DEFAULT_COMMUNITY_RO
                if not device.snmp_community_rw:
                    updates["snmp_community_rw"] = settings.SNMP_DEFAULT_COMMUNITY_RW
                if updates:
                    Device.objects.filter(pk=device.pk).update(**updates)
                summary["updated"] += 1

            logger.info(f"Auto-provisioning host at IP: {ip_address}")
            try:
                run_device_discovery(
                    ip=str(ip_address),
                    community=community,
                    managed_device=device,
                    timeout=timeout,
                    retries=retries,
                )
                summary["discovered"] += 1
            except SnmpReadError as exc:
                summary["failed"] += 1
                logger.warning(
                    "Discovery failed for host (SNMP error)",
                    extra={"ip": ip_address, "error": str(exc)},
                )
            except Exception as exc:
                summary["failed"] += 1
                logger.exception(
                    "Discovery failed for host",
                    extra={"ip": ip_address, "error": str(exc)},
                )

        return summary

    def process_subnets(self):
        return Ats.objects.exclude(subnet__isnull=True).exclude(subnet="").select_related("group").order_by("-pk")

    def handle(self, *args, **options):
        logger.info("Starting SNMP auto-provisioning process...")
        totals = {"created": 0, "updated": 0, "discovered": 0, "failed": 0, "unreachable": 0}

        for ats in self.process_subnets():
            try:
                subnet = IPv4Network(ats.subnet, strict=False)
            except ValueError:
                logger.warning("Skipping invalid subnet", extra={"ats_id": ats.id, "subnet": ats.subnet})
                continue

            # Keep original behavior: split into /25 batches to reduce scan bursts.
            scan_subnets = list(subnet.subnets(new_prefix=25)) if subnet.prefixlen < 25 else [subnet]
            for chunk in scan_subnets:
                summary = self.handle_subnet(
                    chunk,
                    ats,
                    community=options["community"],
                    timeout=options["timeout"],
                    retries=options["retries"],
                    dry_run=options["dry_run"],
                )
                for key in totals:
                    totals[key] += summary[key]

        self.stdout.write(
            self.style.SUCCESS(
                "Auto-provisioning finished: "
                f"created={totals['created']} updated={totals['updated']} "
                f"discovered={totals['discovered']} failed={totals['failed']} "
                f"unreachable={totals['unreachable']}"
            )
        )
