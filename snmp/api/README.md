# SNMP Manager API Documentation

## Overview

REST API для управления сетевыми устройствами и мониторинга оптического сигнала.

**Base URL:** `/api/v1/`

**Authentication:** Token-based (JWT) or Session authentication required for all endpoints.

---

## Endpoints

### Devices (Switches/Routers)

#### List Devices
```
GET /api/v1/devices/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `hostname` | string | Filter by hostname (case-insensitive) |
| `ip` | string | Filter by IP address |
| `status` | boolean | Filter by online status (true/false) |
| `ats` | integer | Filter by ATS ID |
| `branch` | integer | Filter by Branch ID |
| `group` | integer | Filter by HostGroup ID |
| `model` | integer | Filter by DeviceModel ID |
| `search` | string | Global search across hostname, IP, MAC, serial |
| `online` | boolean | Filter online/offline devices |
| `page` | integer | Page number |
| `page_size` | integer | Results per page (default: 25) |

**Response:**
```json
{
  "count": 150,
  "next": "/api/v1/devices/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "hostname": "sw-core-01",
      "ip": "192.168.1.1",
      "device_mac": "00:11:22:33:44:55",
      "status": true,
      "created": "2024-01-01T00:00:00Z",
      "last_update": "2024-01-14T10:00:00Z",
      "uptime": "30 days, 5:23:45",
      "serial_number": "SN123456",
      "soft_version": "15.2(4)M",
      "ats": {"id": 1, "name": "ATS-01", "subnet": "192.168.1.0/24"},
      "model": {"id": 1, "vendor": {"id": 1, "name": "Cisco"}, "device_model": "Catalyst 2960"},
      "group_name": "Core Switches"
    }
  ]
}
```

#### Get Device Detail
```
GET /api/v1/devices/{id}/
```

**Response:** Full device object with interfaces and neighbor links.

#### Create Device
```
POST /api/v1/devices/
```

**Request Body:**
```json
{
  "hostname": "sw-new-01",
  "ip": "192.168.1.100",
  "device_mac": "00:11:22:33:44:66",
  "ats": 1,
  "group": 1,
  "model": 1,
  "snmp_community_ro": "public",
  "snmp_community_rw": "private"
}
```

#### Update Device
```
PUT /api/v1/devices/{id}/
PATCH /api/v1/devices/{id}/
```

#### Delete Device
```
DELETE /api/v1/devices/{id}/
```

#### Get Device Ports
```
GET /api/v1/devices/{id}/ports/
```

Returns all interfaces for a specific device.

#### Get Device Neighbors
```
GET /api/v1/devices/{id}/neighbors/
```

Returns all neighbor links for a specific device.

---

### Optical Signal Monitoring

#### List Optical Interfaces
```
GET /api/v1/optical/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `device` | integer | Filter by Device ID |
| `device_hostname` | string | Filter by device hostname |
| `device_ip` | string | Filter by device IP |
| `branch` | integer | Filter by Branch ID |
| `ats` | integer | Filter by ATS ID |
| `rx_dbm_lte` | float | RX signal less than or equal |
| `rx_dbm_gte` | float | RX signal greater than or equal |
| `signal_status` | string | Filter by status: `critical`, `warning`, `normal`, `unknown` |
| `sfp_vendor` | string | Filter by SFP vendor |
| `has_optics` | boolean | Filter interfaces with optics data |
| `search` | string | Global search |

**Response:**
```json
{
  "count": 500,
  "results": [
    {
      "id": 123,
      "device_id": 1,
      "device_hostname": "sw-core-01",
      "device_ip": "192.168.1.1",
      "branch_name": "Main Office",
      "ats_name": "ATS-01",
      "model_name": "Catalyst 2960",
      "ifindex": 25,
      "name": "GigabitEthernet0/25",
      "description": "Uplink to Core",
      "rx_dbm": -12.5,
      "tx_dbm": -3.2,
      "temperature_c": 35.5,
      "voltage_v": 3.3,
      "sfp_vendor": "Cisco",
      "part_number": "GLC-LH-SMD",
      "serial_number": "SFP123456",
      "optics_polled_at": "2024-01-14T10:00:00Z",
      "signal_status": "normal"
    }
  ]
}
```

#### Get Optical Summary
```
GET /api/v1/optical/summary/
```

**Response:**
```json
{
  "total_optical_ports": 500,
  "ports_with_signal": 480,
  "critical_ports": 5,
  "warning_ports": 15,
  "normal_ports": 460,
  "unknown_ports": 20,
  "avg_rx_dbm": -14.5,
  "min_rx_dbm": -28.3,
  "max_rx_dbm": -8.1,
  "last_updated": "2024-01-14T10:00:00Z"
}
```

#### List Critical Signals
```
GET /api/v1/optical/critical/
```

Returns interfaces with RX signal ≤ -25 dBm.

#### List Warning Signals
```
GET /api/v1/optical/warning/
```

Returns interfaces with -25 < RX signal ≤ -20 dBm.

#### Get Optical by Device
```
GET /api/v1/optical/by-device/{device_id}/
```

Returns all optical interfaces for a specific device.

#### Get Optical by Branch
```
GET /api/v1/optical/by-branch/{branch_id}/
```

Returns all optical interfaces for a specific branch.

#### Export Optical Data
```
GET /api/v1/optical/export/
```

Exports up to 1000 records as JSON for CSV/Excel generation.

**Response:**
```json
{
  "count": 500,
  "exported_at": "2024-01-14T10:00:00Z",
  "data": [...]
}
```

---

### Interfaces

#### List Interfaces
```
GET /api/v1/interfaces/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `device` | integer | Filter by Device ID |
| `device_hostname` | string | Filter by device hostname |
| `ifindex` | integer | Filter by interface index |
| `oper` | integer | Filter by operational status (1=up, 2=down) |
| `admin` | integer | Filter by admin status |
| `has_optics` | boolean | Filter interfaces with optics |

---

### Neighbor Links

#### List Neighbors
```
GET /api/v1/neighbors/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `local_device` | integer | Filter by local device ID |
| `remote_mac` | string | Filter by remote MAC address |

---

### Bandwidth Samples

#### List Bandwidth Samples
```
GET /api/v1/bandwidth/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `device` | integer | Filter by Device ID |
| `interface` | integer | Filter by Interface ID |
| `ts_after` | datetime | Filter samples after timestamp |
| `ts_before` | datetime | Filter samples before timestamp |
| `in_bps_gte` | integer | Filter by minimum input bps |
| `out_bps_gte` | integer | Filter by minimum output bps |

---

### Dashboard

#### Get Statistics
```
GET /api/v1/dashboard/statistics/
```

**Response:**
```json
{
  "total_devices": 150,
  "online_devices": 145,
  "offline_devices": 5,
  "total_ports": 3000,
  "active_ports": 2500,
  "total_branches": 10,
  "total_ats": 50,
  "uptime_percentage": 96.67,
  "last_updated": "2024-01-14T10:00:00Z"
}
```

---

### Reference Data

#### Branches
```
GET /api/v1/branches/
POST /api/v1/branches/
GET /api/v1/branches/{id}/
PUT /api/v1/branches/{id}/
DELETE /api/v1/branches/{id}/
```

#### ATS (Access Terminal Stations)
```
GET /api/v1/ats/
POST /api/v1/ats/
GET /api/v1/ats/{id}/
PUT /api/v1/ats/{id}/
DELETE /api/v1/ats/{id}/
```

#### Vendors
```
GET /api/v1/vendors/
POST /api/v1/vendors/
GET /api/v1/vendors/{id}/
PUT /api/v1/vendors/{id}/
DELETE /api/v1/vendors/{id}/
```

#### Device Models
```
GET /api/v1/device-models/
POST /api/v1/device-models/
GET /api/v1/device-models/{id}/
PUT /api/v1/device-models/{id}/
DELETE /api/v1/device-models/{id}/
```

#### Host Groups
```
GET /api/v1/host-groups/
POST /api/v1/host-groups/
GET /api/v1/host-groups/{id}/
PUT /api/v1/host-groups/{id}/
DELETE /api/v1/host-groups/{id}/
```

---

## Signal Level Thresholds

| Status | RX Level (dBm) | Color |
|--------|----------------|-------|
| **Critical** | ≤ -25 | Red |
| **Warning** | -25 to -20 | Yellow |
| **Normal** | > -20 | Green |
| **Unknown** | No data | Gray |

---

## Error Responses

All errors follow this format:
```json
{
  "success": false,
  "error": "Error message",
  "status_code": 400
}
```

**Common Status Codes:**
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid credentials)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `500` - Internal Server Error

---

## Backward Compatibility

The following deprecated endpoints are still available:
- `/api/v1/switches/` → redirects to `/api/v1/devices/`
- `/api/v1/switch-models/` → redirects to `/api/v1/device-models/`

These aliases will be removed in a future version.
