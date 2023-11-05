from pysnmp.hlapi import *
import os
import sqlite3


conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()


community = 'snmp2netread'
switches = []

with open("list.txt", "r") as file:
    for line in file:
        ip = line.strip()
        switches.append(ip)


for ip in switches:
    host = os.system("ping -c 1 " + ip)
    if not host:
        continue
    
    for (errorIndication,
        errorStatus,
        errorIndex,
        varBinds) in bulkCmd(SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((host, 161)),
            ContextData(),
            0, 25,  # fetch up to 25 OIDs one-shot
            ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'))):
        if errorIndication or errorStatus:
            print(errorIndication or errorStatus)
            break
        else:
            for varBind in varBinds:
                print(' = '.join([x.prettyPrint() for x in varBind]))
                
        def insert_transceiver_info(ip, vendor, lvl):
            try:
                cursor.execute("INSERT INTO cdfrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr (Switch_ip, TransVendor, Signal) VALUES (?, ?, ?)", (ip, vendor, lvl))
                conn.commit()
            except Exception as e:
                print(f"Error while inserting data into the database: {str(e)}")