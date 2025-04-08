from snmp.models import SwitchPort

def filter_ports_by_criteria():
    # Получение всех портов, фильтруя на основе нужных критериев (например, исключение loopback, tunnel)
    ports = SwitchPort.objects.exclude(description__regex=r'(loopback|tunnel|null)')
    return ports
