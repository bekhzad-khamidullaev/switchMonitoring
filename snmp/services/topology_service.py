"""
Service for network topology operations.
Handles topology mapping, visualization data generation.
"""
import logging
from typing import List, Dict
from django.db.models import Prefetch, Max
from django.db import models

from snmp.models import Switch, NeighborLink as SwitchNeighbor, HostGroup, Branch

logger = logging.getLogger(__name__)


class TopologyService:
    """Service for network topology operations."""
    
    @staticmethod
    def generate_topology_data(filters=None) -> Dict:
        """
        Generate topology data for network visualization.
        
        Args:
            filters: Optional filters for switches
            
        Returns:
            Dictionary with nodes, edges, and groups
        """
        queryset = Switch.objects.filter(is_active=True).select_related(
            'ats', 'branch', 'host_group', 'device_model'
        ).prefetch_related(
            Prefetch('switchneighbor_set', queryset=SwitchNeighbor.objects.select_related('port'))
        )
        
        if filters:
            queryset = queryset.filter(**filters)
        
        nodes = []
        edges = []
        groups = {}
        
        # Build nodes
        for switch in queryset:
            node = {
                'id': switch.id,
                'label': switch.name,
                'ip_address': switch.ip_address,
                'status': switch.status,
                'type': 'switch',
                'group': switch.host_group.name if switch.host_group else 'Ungrouped',
                'branch': switch.branch.name if switch.branch else None,
                'ats': switch.ats.name if switch.ats else None,
                'model': switch.device_model.model if switch.device_model else None,
                'metrics': {
                    'cpu_usage': switch.cpu_usage,
                    'memory_usage': switch.memory_usage,
                    'temperature': switch.temperature,
                },
                'location': {
                    'latitude': float(switch.branch.latitude) if switch.branch and switch.branch.latitude else None,
                    'longitude': float(switch.branch.longitude) if switch.branch and switch.branch.longitude else None,
                }
            }
            nodes.append(node)
            
            # Track groups
            group_name = switch.host_group.name if switch.host_group else 'Ungrouped'
            if group_name not in groups:
                groups[group_name] = {
                    'name': group_name,
                    'nodes': [],
                    'color': TopologyService._get_group_color(len(groups))
                }
            groups[group_name]['nodes'].append(switch.id)
        
        # Build edges from neighbors
        processed_connections = set()
        
        for switch in queryset:
            for neighbor in switch.switchneighbor_set.all():
                # Try to find neighbor in our switch list
                neighbor_switch = None
                if neighbor.neighbor_system_name:
                    neighbor_switch = Switch.objects.filter(
                        name__icontains=neighbor.neighbor_system_name
                    ).first()
                
                if neighbor_switch:
                    # Create edge between switches
                    edge_key = tuple(sorted([switch.id, neighbor_switch.id]))
                    
                    if edge_key not in processed_connections:
                        edges.append({
                            'id': f"edge_{switch.id}_{neighbor_switch.id}",
                            'from': switch.id,
                            'to': neighbor_switch.id,
                            'label': neighbor.port.port_name if neighbor.port else '',
                            'protocol': neighbor.protocol,
                            'type': 'neighbor',
                        })
                        processed_connections.add(edge_key)
        
        return {
            'nodes': nodes,
            'edges': edges,
            'groups': list(groups.values()),
            'statistics': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'total_groups': len(groups),
            }
        }
    
    @staticmethod
    def _get_group_color(index: int) -> str:
        """Get color for a group based on index."""
        colors = [
            '#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
            '#1abc9c', '#34495e', '#e67e22', '#95a5a6', '#d35400'
        ]
        return colors[index % len(colors)]
    
    @staticmethod
    def generate_hierarchical_topology() -> Dict:
        """
        Generate hierarchical topology based on host groups.
        
        Returns:
            Dictionary with hierarchical structure
        """
        root_groups = HostGroup.objects.filter(parent__isnull=True).prefetch_related(
            'children', 'switch_set'
        )
        
        def build_tree(group):
            """Recursively build tree structure."""
            node = {
                'id': f'group_{group.id}',
                'name': group.name,
                'type': 'group',
                'level': group.level,
                'children': [],
                'switches': []
            }
            
            # Add switches in this group
            for switch in group.switch_set.filter(is_active=True):
                node['switches'].append({
                    'id': switch.id,
                    'name': switch.name,
                    'ip_address': switch.ip_address,
                    'status': switch.status,
                })
            
            # Add child groups
            for child in group.children.all():
                node['children'].append(build_tree(child))
            
            return node
        
        hierarchy = []
        for root in root_groups:
            hierarchy.append(build_tree(root))
        
        return {
            'hierarchy': hierarchy,
            'total_groups': HostGroup.objects.count(),
            'max_depth': HostGroup.objects.aggregate(
                max_level=models.Max('level')
            )['max_level'] or 0
        }
    
    @staticmethod
    def generate_geographical_topology() -> Dict:
        """
        Generate topology data for geographical map visualization.
        
        Returns:
            Dictionary with geographical data
        """
        branches = Branch.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).prefetch_related('switch_set')
        
        locations = []
        
        for branch in branches:
            switches = branch.switch_set.filter(is_active=True)
            
            location = {
                'id': branch.id,
                'name': branch.name,
                'address': branch.address,
                'latitude': float(branch.latitude),
                'longitude': float(branch.longitude),
                'switches': {
                    'total': switches.count(),
                    'online': switches.filter(status='online').count(),
                    'offline': switches.filter(status='offline').count(),
                },
                'contact': {
                    'person': branch.contact_person,
                    'phone': branch.phone,
                    'email': branch.email,
                }
            }
            
            locations.append(location)
        
        return {
            'locations': locations,
            'total_locations': len(locations),
        }
    
    @staticmethod
    def find_path_between_switches(source_id: int, target_id: int) -> Dict:
        """
        Find network path between two switches.
        
        Args:
            source_id: Source switch ID
            target_id: Target switch ID
            
        Returns:
            Dictionary with path information
        """
        source = Switch.objects.get(id=source_id)
        target = Switch.objects.get(id=target_id)
        
        # Simple BFS to find path
        from collections import deque
        
        visited = set()
        queue = deque([(source, [source])])
        
        while queue:
            current, path = queue.popleft()
            
            if current.id == target_id:
                # Found path
                return {
                    'found': True,
                    'path': [
                        {
                            'id': s.id,
                            'name': s.name,
                            'ip_address': s.ip_address
                        } for s in path
                    ],
                    'hops': len(path) - 1
                }
            
            if current.id in visited:
                continue
            
            visited.add(current.id)
            
            # Get neighbors
            for neighbor in current.switchneighbor_set.all():
                if neighbor.neighbor_system_name:
                    neighbor_switch = Switch.objects.filter(
                        name__icontains=neighbor.neighbor_system_name
                    ).first()
                    
                    if neighbor_switch and neighbor_switch.id not in visited:
                        queue.append((neighbor_switch, path + [neighbor_switch]))
        
        return {
            'found': False,
            'message': 'No path found between switches'
        }
    
    @staticmethod
    def get_switch_connections(switch_id: int) -> Dict:
        """
        Get all connections for a specific switch.
        
        Args:
            switch_id: ID of switch
            
        Returns:
            Dictionary with connection information
        """
        switch = Switch.objects.prefetch_related(
            'switchneighbor_set__port'
        ).get(id=switch_id)
        
        connections = []
        
        for neighbor in switch.switchneighbor_set.all():
            connection = {
                'local_port': neighbor.port.port_name if neighbor.port else 'Unknown',
                'remote_device': neighbor.neighbor_system_name or neighbor.neighbor_device_id,
                'remote_port': neighbor.neighbor_port_id,
                'protocol': neighbor.protocol,
                'last_seen': neighbor.last_seen,
            }
            
            # Try to find remote switch in database
            if neighbor.neighbor_system_name:
                remote_switch = Switch.objects.filter(
                    name__icontains=neighbor.neighbor_system_name
                ).first()
                if remote_switch:
                    connection['remote_switch_id'] = remote_switch.id
                    connection['remote_ip'] = remote_switch.ip_address
                    connection['remote_status'] = remote_switch.status
            
            connections.append(connection)
        
        return {
            'switch_id': switch.id,
            'switch_name': switch.name,
            'connections': connections,
            'total_connections': len(connections),
        }
    
    @staticmethod
    def detect_topology_loops() -> List[Dict]:
        """
        Detect potential loops in network topology.
        
        Returns:
            List of detected loops
        """
        loops = []
        
        # Get all switches with neighbors
        switches = Switch.objects.filter(
            is_active=True
        ).prefetch_related('switchneighbor_set')
        
        # Simple cycle detection using DFS
        def dfs(switch, visited, path):
            visited.add(switch.id)
            path.append(switch)
            
            for neighbor in switch.switchneighbor_set.all():
                if neighbor.neighbor_system_name:
                    neighbor_switch = Switch.objects.filter(
                        name__icontains=neighbor.neighbor_system_name
                    ).first()
                    
                    if neighbor_switch:
                        if neighbor_switch.id in [s.id for s in path]:
                            # Found a loop
                            loop_start_idx = next(
                                i for i, s in enumerate(path)
                                if s.id == neighbor_switch.id
                            )
                            loop = path[loop_start_idx:]
                            loops.append({
                                'switches': [
                                    {'id': s.id, 'name': s.name}
                                    for s in loop
                                ],
                                'length': len(loop)
                            })
                        elif neighbor_switch.id not in visited:
                            dfs(neighbor_switch, visited, path[:])
        
        visited = set()
        for switch in switches:
            if switch.id not in visited:
                dfs(switch, visited, [])
        
        return loops
