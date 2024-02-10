import telnetlib
import logging
import re
import sqlite3


conn = sqlite3.connect("transceiver_info.db")
cursor = conn.cursor()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IfaceInfo")

cursor.execute('''
    CREATE TABLE IF NOT EXISTS transceiver_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Switch_ip TEXT,
        TransVendor TEXT,
        Signal lvl TXT,
        Interface TXT
    )
''')

###############################################################################
###############################################################################
###############################################################################

def establish_telnet_connection(host, port, username, password):
    try:
        tn = telnetlib.Telnet(host, port, timeout=1)
        tn.read_until(b"name: ", timeout=1)
        tn.write(username.encode('utf-8') + b"\n")
        tn.read_until(b"Password: ", timeout=1)
        tn.write(password.encode('utf-8') + b"\n")
        prompt = tn.read_until(b'[>#]', timeout=1).decode('utf-8')
        return tn, prompt
    except Exception as e:
        logger.error(f"Failed to establish Telnet connection: {str(e)}")
        return None


def send_telnet_command(tn, command):
    try:
        tn.write(command.encode('utf-8') + b"\n")
        index, match, response = tn.expect([b'[>#]'])
        response = response.decode('utf-8', errors='replace')
        if index == -1:
            logger.error(f"Failed to match the expected pattern: [>#]")
            return None
        logger.info(f'Sent command: {command}\nResponse: {response}')
        return response
    except Exception as e:
        logger.error(f"Error while sending Telnet command: {str(e)}")
        return None

###############################################################################
###############################################################################
###############################################################################

# def get_switch_hostname(tn):
#     try:
#         tn.write(b"show system information\n")
#         response = tn.read_until(b'#', timeout=5)
#         response = response.decode('utf-8', errors='replace')
#         hostname_match = re.search(r'Hostname\s+:\s+(.*?)\n', response)
#         if hostname_match:
#             return hostname_match.group(1).strip()
#         else:
#             logger.error("Failed to retrieve the hostname.")
#     except Exception as e:
#         logger.error(f"Error while getting the hostname: {str(e)}")
#     return "N/A"



###############################################################################
######################### HUAWEI ##############################################
###############################################################################

def extract_transceiver_info_huawei(output, interface_name):
    transceiver_info = []

    transceiver_sections = re.findall(rf'{interface_name} transceiver information:[\s\S]*?(?=(?:\nInterface Name|$))', output)
    for section in transceiver_sections:
        info = {}
        info['Interface Name'] = re.search(r'(\S+) transceiver information:', section).group(1)
        vendor_match = re.search(r'Vendor Name\s+:(.*?)\n', section)
        rx_power_match = re.search(r'RX Power\(dBM\)\s+:(.*?)\n', section)
        info['Vendor Name'] = vendor_match.group(1).strip() if vendor_match else "N/A"
        info['RX Power (dBm)'] = rx_power_match.group(1).strip() if rx_power_match else "N/A"
        transceiver_info.append(info)

    return transceiver_info

def get_required_transceiver_info_huawei(tn):
    try:
        if tn:
            output = send_telnet_command(tn, "display transceiver interface GigabitEthernet0/0/1 verbose")
            tn.write(b"quit\n")
            tn.close()

            if output:
                transceiver_info = extract_transceiver_info_huawei(output, "GigabitEthernet0/0/1")
                return transceiver_info
            else:
                logger.error("Failed to retrieve transceiver info.")
        else:
            logger.error("Error: Failed to establish a Telnet connection.")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    return []

###############################################################################
######################### ZYXEL ###############################################
###############################################################################

def extract_transceiver_info_zyxel(output):
    transceiver_info = []
    section_pattern = r'Port\s*:\s*\d+.*?(?=(?:Port\s*:\s*\d+|$))'
    sections = re.findall(section_pattern, output, re.DOTALL)

    for section in sections:
        info = {}
        vendor_match = re.search(r'Vendor\s*:?\s*(.*?)\n', section)
        rx_power_match = re.search(r'RX Power\(dbm\)\s*:?\s*(.*?)\n', section)
        if rx_power_match:
            rx_power_values = rx_power_match.group(1).strip().split()
            print(rx_power_values[0])
            if rx_power_values:
                info['RX Power (dBm)'] = rx_power_values[0]
            else:
                info['RX Power (dBm)'] = "N/A"
        else:
            info['RX Power (dBm)'] = "N/A"
        info['Vendor Name'] = vendor_match.group(1).strip() if vendor_match else "N/A"
        transceiver_info.append(info)

    return transceiver_info

def get_required_transceiver_info_zyxel(tn):
    try:
        if tn:
            output = send_telnet_command(tn, "show interfaces transceiver 25")
            tn.write(b"exit\n")
            tn.close()

            if output:
                transceiver_info = extract_transceiver_info_zyxel(output)
                logger.info(transceiver_info)
                return transceiver_info
            else:
                logger.error("Failed to retrieve transceiver info.")
        else:
            print("Error: Failed to establish a Telnet connection.")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    return []

###############################################################################
###############################################################################
###############################################################################

def insert_transceiver_info(ip, vendor, lvl):
    try:
        cursor.execute("INSERT INTO transceiver_info (Switch_ip, TransVendor, Signal) VALUES (?, ?, ?)", (ip, vendor, lvl))
        conn.commit()
    except Exception as e:
        logger.error(f"Error while inserting data into the database: {str(e)}")

# Main script
switches = []
with open("list.txt", "r") as file:
    for line in file:
        ip = line.strip()
        switches.append(ip)

username = "bekhzad"
password = "adminadmin"
port = 23
all_results = []

for ip in switches:
    if not ip:
        continue

    # Establish the Telnet connection and get the prompt
    tn, prompt = establish_telnet_connection(ip, port, username, password)

    if tn:
        if '#' in prompt:
            results = get_required_transceiver_info_zyxel(tn)
        if '>' in prompt:
            results = get_required_transceiver_info_huawei(tn)
    
        for result in results:
            vendor = result['Vendor Name']
            lvl = result['RX Power (dBm)'] 
            insert_transceiver_info(ip, vendor, lvl)
        

# Close the database connection when done
conn.close()
