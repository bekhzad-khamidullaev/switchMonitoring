"""
Unit tests for service layer.
Tests business logic in services.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch

from snmp.models import (
    ATS, Branch, HostGroup, Switch, SwitchPort,
    SwitchModel, BandwidthSample
)
from snmp.services.switch_service import SwitchService
from snmp.services.monitoring_service import MonitoringService
from snmp.services.discovery_service import DiscoveryService
from snmp.services.topology_service import TopologyService

User = get_user_model()


class SwitchServiceTest(TestCase):
    """Test SwitchService."""
    
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test123')
        self.ats = ATS.objects.create(name='Test ATS', code='ATS001', subnet='192.168.1.0/24')
        self.branch = Branch.objects.create(name='Test Branch', code='BR001', ats=self.ats)
        self.switch = Switch.objects.create(
            name='Test Switch',
            ip_address='192.168.1.1',
            ats=self.ats,
            branch=self.branch,
            status='online'
        )
    
    def test_create_switch(self):
        """Test creating a switch."""
        data = {
            'name': 'New Switch',
            'ip_address': '192.168.1.2',
            'ats': self.ats,
            'branch': self.branch,
            'status': 'online'
        }
        switch = SwitchService.create_switch(data, self.user)
        self.assertIsNotNone(switch.id)
        self.assertEqual(switch.name, 'New Switch')
    
    def test_update_switch(self):
        """Test updating a switch."""
        data = {'description': 'Updated description'}
        updated = SwitchService.update_switch(self.switch.id, data, self.user)
        self.assertEqual(updated.description, 'Updated description')
    
    def test_get_switch_status(self):
        """Test getting switch status."""
        # Create some ports
        for i in range(5):
            SwitchPort.objects.create(
                switch=self.switch,
                port_index=i+1,
                port_name=f'Port{i+1}',
                status='up' if i < 3 else 'down'
            )
        
        status = SwitchService.get_switch_status(self.switch.id)
        self.assertEqual(status['id'], self.switch.id)
        self.assertEqual(status['ports']['total'], 5)
        self.assertEqual(status['ports']['up'], 3)
        self.assertEqual(status['ports']['down'], 2)
    
    def test_get_switches_with_issues(self):
        """Test getting switches with issues."""
        # Create switch with high CPU
        Switch.objects.create(
            name='High CPU Switch',
            ip_address='192.168.1.10',
            ats=self.ats,
            branch=self.branch,
            cpu_usage=95,
            status='online'
        )
        
        switches = SwitchService.get_switches_with_issues()
        self.assertGreater(switches.count(), 0)
    
    def test_search_switches(self):
        """Test searching switches."""
        results = SwitchService.search_switches('Test')
        self.assertGreater(results.count(), 0)
        self.assertIn(self.switch, results)
    
    def test_get_switch_statistics(self):
        """Test getting switch statistics."""
        stats = SwitchService.get_switch_statistics()
        self.assertIn('total', stats)
        self.assertIn('online', stats)
        self.assertGreater(stats['total'], 0)
    
    def test_bulk_update_switches(self):
        """Test bulk updating switches."""
        switch2 = Switch.objects.create(
            name='Switch 2',
            ip_address='192.168.1.2',
            ats=self.ats,
            branch=self.branch
        )
        
        count = SwitchService.bulk_update_switches(
            [self.switch.id, switch2.id],
            {'is_monitored': True},
            self.user
        )
        self.assertEqual(count, 2)
        
        self.switch.refresh_from_db()
        self.assertTrue(self.switch.is_monitored)


class MonitoringServiceTest(TestCase):
    """Test MonitoringService."""
    
    def setUp(self):
        self.ats = ATS.objects.create(name='Test ATS', code='ATS001', subnet='192.168.1.0/24')
        self.branch = Branch.objects.create(name='Test Branch', code='BR001', ats=self.ats)
        self.switch = Switch.objects.create(
            name='Test Switch',
            ip_address='192.168.1.1',
            ats=self.ats,
            branch=self.branch,
            snmp_community_ro='public',
            snmp_version='2c',
            status='online'
        )
        self.port = SwitchPort.objects.create(
            switch=self.switch,
            port_index=1,
            port_name='GigabitEthernet0/1',
            status='up'
        )
    
    @patch('snmp.services.monitoring_service.SNMPClient')
    def test_poll_switch(self, mock_client):
        """Test polling a switch."""
        # Mock SNMP client
        mock_instance = Mock()
        mock_instance.get.side_effect = [
            'Test Device Description',  # sysDescr
            12345678,                    # sysUpTime
            'TestSwitch'                 # sysName
        ]
        mock_instance.walk.return_value = []
        mock_client.return_value = mock_instance
        
        result = MonitoringService.poll_switch(self.switch.id)
        self.assertIsNotNone(result)
        
        self.switch.refresh_from_db()
        self.assertEqual(self.switch.status, 'online')
    
    def test_get_switch_health_report(self):
        """Test generating health report."""
        report = MonitoringService.get_switch_health_report(self.switch.id)
        self.assertEqual(report['switch_id'], self.switch.id)
        self.assertIn('health_score', report)
        self.assertIn('issues', report)
        self.assertIn('warnings', report)
    
    def test_get_switches_requiring_attention(self):
        """Test getting switches requiring attention."""
        # Create offline switch
        Switch.objects.create(
            name='Offline Switch',
            ip_address='192.168.1.10',
            ats=self.ats,
            branch=self.branch,
            status='offline'
        )
        
        switches = MonitoringService.get_switches_requiring_attention()
        self.assertGreater(switches.count(), 0)


class DiscoveryServiceTest(TestCase):
    """Test DiscoveryService."""
    
    def setUp(self):
        self.ats = ATS.objects.create(name='Test ATS', code='ATS001', subnet='192.168.1.0/24')
        self.branch = Branch.objects.create(name='Test Branch', code='BR001', ats=self.ats)
    
    @patch('snmp.services.discovery_service.SNMPClient')
    def test_probe_device(self, mock_client):
        """Test probing a device."""
        mock_instance = Mock()
        mock_instance.get.side_effect = [
            'Cisco IOS Device',      # sysDescr
            'TestSwitch',            # sysName
            12345678,                # sysUpTime
            'admin@example.com',     # sysContact
            'Data Center'            # sysLocation
        ]
        mock_client.return_value = mock_instance
        
        result = DiscoveryService._probe_device(
            '192.168.1.1',
            'public',
            '2c',
            2
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['ip_address'], '192.168.1.1')
        self.assertEqual(result['sysName'], 'TestSwitch')
    
    def test_identify_device_model(self):
        """Test identifying device model from description."""
        # Create known model
        SwitchModel.objects.create(
            vendor='Cisco',
            model='Catalyst 2960'
        )
        
        model = DiscoveryService._identify_device_model(
            'Cisco IOS Software, C2960 Software'
        )
        self.assertIsNotNone(model)
        self.assertEqual(model.vendor, 'Cisco')
    
    def test_auto_create_switches(self):
        """Test auto-creating switches from discovered devices."""
        devices = [
            {
                'ip_address': '192.168.1.10',
                'sysName': 'Switch1',
                'sysDescr': 'Test Device',
                'snmp_community': 'public',
                'snmp_version': '2c'
            },
            {
                'ip_address': '192.168.1.11',
                'sysName': 'Switch2',
                'sysDescr': 'Test Device',
                'snmp_community': 'public',
                'snmp_version': '2c'
            }
        ]
        
        results = DiscoveryService.auto_create_switches(
            devices,
            default_ats=self.ats,
            default_branch=self.branch
        )
        
        self.assertEqual(results['total'], 2)
        self.assertEqual(results['created'], 2)
        self.assertEqual(Switch.objects.count(), 2)


class TopologyServiceTest(TestCase):
    """Test TopologyService."""
    
    def setUp(self):
        self.ats = ATS.objects.create(name='Test ATS', code='ATS001', subnet='192.168.1.0/24')
        self.branch = Branch.objects.create(name='Test Branch', code='BR001', ats=self.ats)
        self.host_group = HostGroup.objects.create(name='Test Group', level=0)
        
        # Create switches
        self.switch1 = Switch.objects.create(
            name='Switch1',
            ip_address='192.168.1.1',
            ats=self.ats,
            branch=self.branch,
            host_group=self.host_group,
            is_active=True
        )
        self.switch2 = Switch.objects.create(
            name='Switch2',
            ip_address='192.168.1.2',
            ats=self.ats,
            branch=self.branch,
            host_group=self.host_group,
            is_active=True
        )
    
    def test_generate_topology_data(self):
        """Test generating topology data."""
        topology = TopologyService.generate_topology_data()
        
        self.assertIn('nodes', topology)
        self.assertIn('edges', topology)
        self.assertIn('groups', topology)
        self.assertEqual(len(topology['nodes']), 2)
    
    def test_generate_hierarchical_topology(self):
        """Test generating hierarchical topology."""
        # Create child group
        child_group = HostGroup.objects.create(
            name='Child Group',
            parent=self.host_group,
            level=1
        )
        
        topology = TopologyService.generate_hierarchical_topology()
        self.assertIn('hierarchy', topology)
        self.assertGreater(topology['total_groups'], 0)
    
    def test_get_switch_connections(self):
        """Test getting switch connections."""
        # Create neighbor
        port = SwitchPort.objects.create(
            switch=self.switch1,
            port_index=1,
            port_name='Port1'
        )
        from snmp.models import SwitchNeighbor
        SwitchNeighbor.objects.create(
            switch=self.switch1,
            port=port,
            neighbor_system_name='Switch2',
            neighbor_device_id='switch2-id',
            protocol='lldp'
        )
        
        connections = TopologyService.get_switch_connections(self.switch1.id)
        self.assertEqual(connections['switch_id'], self.switch1.id)
        self.assertEqual(connections['total_connections'], 1)


class ServiceIntegrationTest(TestCase):
    """Integration tests for services working together."""
    
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test123')
        self.ats = ATS.objects.create(name='Test ATS', code='ATS001', subnet='192.168.1.0/24')
        self.branch = Branch.objects.create(name='Test Branch', code='BR001', ats=self.ats)
    
    def test_create_and_monitor_switch(self):
        """Test creating a switch and then monitoring it."""
        # Create switch
        data = {
            'name': 'New Switch',
            'ip_address': '192.168.1.1',
            'ats': self.ats,
            'branch': self.branch,
            'snmp_community_ro': 'public',
            'snmp_version': '2c',
            'is_monitored': True
        }
        switch = SwitchService.create_switch(data, self.user)
        
        # Get status
        status = SwitchService.get_switch_status(switch.id)
        self.assertIsNotNone(status)
        self.assertEqual(status['name'], 'New Switch')
    
    def test_discover_and_create_topology(self):
        """Test discovering switches and generating topology."""
        # Create some switches
        for i in range(3):
            Switch.objects.create(
                name=f'Switch{i}',
                ip_address=f'192.168.1.{i+1}',
                ats=self.ats,
                branch=self.branch,
                is_active=True
            )
        
        # Generate topology
        topology = TopologyService.generate_topology_data()
        self.assertEqual(len(topology['nodes']), 3)
