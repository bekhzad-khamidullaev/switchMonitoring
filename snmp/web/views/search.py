from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from snmp.models import Mac
from snmp.web.views.access import get_permitted_groups, user_has_global_device_access

_ORDERING_MAP = {
    0: "managed_device__hostname",
    1: "port__port",
    2: "vlan",
    3: "ip",
    4: "data",
    5: "mac",
}


def _bool_from_param(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _base_queryset(user):
    queryset = (
        Mac.objects.select_related("managed_device", "port")
        .exclude(managed_device__isnull=True)
        .exclude(port__isnull=True)
    )
    if user_has_global_device_access(user):
        return queryset
    return queryset.filter(managed_device__group__in=get_permitted_groups(user))


def _apply_search(queryset, search_query, filter_ip):
    if filter_ip:
        queryset = queryset.exclude(ip__isnull=True).exclude(ip="")

    normalized = (search_query or "").strip()
    if not normalized:
        return queryset
    if len(normalized) < 3:
        return queryset.none()

    return queryset.filter(
        Q(mac__istartswith=normalized)
        | Q(ip__istartswith=normalized)
        | Q(managed_device__hostname__icontains=normalized)
        | Q(managed_device__ip__istartswith=normalized)
    )


def _apply_ordering(queryset, order_column, order_dir):
    field_name = _ORDERING_MAP.get(order_column, "data")
    if str(order_dir).lower() == "asc":
        return queryset.order_by(field_name)
    return queryset.order_by(f"-{field_name}")


@login_required
@permission_required("snmp.view_device", raise_exception=True)
def mac_ip_search_report(request):
    if request.method == "POST":
        return _mac_ip_search_datatable(request)
    return _mac_ip_search_page(request)


def _mac_ip_search_page(request):
    search_query = (request.GET.get("q") or "").strip()
    filter_ip = _bool_from_param(request.GET.get("filter_ip"))

    rows = []
    if search_query:
        queryset = _apply_search(_base_queryset(request.user), search_query, filter_ip).order_by("-data")
        rows = list(queryset[:200])

    return render(
        request,
        "mac_ip_search.html",
        {
            "rows": rows,
            "search_query": search_query,
            "filter_ip": filter_ip,
        },
    )


def _mac_ip_search_datatable(request):
    draw_raw = request.POST.get("draw", "0")
    try:
        draw = int(draw_raw)
    except ValueError:
        draw = 0

    search_query = (
        request.POST.get("search[value]")
        or request.POST.get("search")
        or ""
    ).strip()
    filter_ip = _bool_from_param(request.POST.get("filter_ip"))

    order_column_raw = request.POST.get("order[0][column]", "4")
    try:
        order_column = int(order_column_raw)
    except ValueError:
        order_column = 4
    order_dir = request.POST.get("order[0][dir]", "desc")

    start_raw = request.POST.get("start", "0")
    length_raw = request.POST.get("length", "100")
    try:
        start = max(int(start_raw), 0)
    except ValueError:
        start = 0
    try:
        length = max(min(int(length_raw), 500), 1)
    except ValueError:
        length = 100

    base = _base_queryset(request.user)
    filtered = _apply_search(base, search_query, filter_ip)
    ordered = _apply_ordering(filtered, order_column=order_column, order_dir=order_dir)

    paginator = Paginator(ordered, length)
    page_number = (start // length) + 1
    page = paginator.get_page(page_number)

    data = [
        {
            "switch": row.managed_device.hostname or str(row.managed_device.ip),
            "port": row.port.port if row.port_id else None,
            "vlan": row.vlan,
            "ip": row.ip or "",
            "data": row.data.isoformat() if row.data else "",
            "mac": row.mac,
        }
        for row in page.object_list
    ]

    return JsonResponse(
        {
            "draw": draw,
            "recordsTotal": base.count(),
            "recordsFiltered": filtered.count(),
            "data": data,
        }
    )
