from pyzabbix import ZabbixAPI

ZABBIX_SERVER = 'https://monitoring.tshtt.uz/'
ZABBIX_USER = 'sit_b.hamidullaev'
ZABBIX_PASSWORD = '946447477'

def get_zabbix_hosts():
    zapi = ZabbixAPI(ZABBIX_SERVER)
    zapi.login(ZABBIX_USER, ZABBIX_PASSWORD)
    
    hosts = zapi.host.get(output=['hostid', 'name'])
    return hosts

def get_zabbix_metrics(host_id):
    zapi = ZabbixAPI(ZABBIX_SERVER)
    zapi.login(ZABBIX_USER, ZABBIX_PASSWORD)
    
    metrics = zapi.item.get(output=['itemid', 'name', 'lastvalue'], hostids=host_id)
    return metrics
