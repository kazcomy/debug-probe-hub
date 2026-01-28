#!/usr/bin/env python3
"""
Configuration loader for Debugger Station
"""
import yaml
from pathlib import Path
from typing import Dict, List, Optional

class Config:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent / 'config.yml'

        with open(config_path, 'r') as f:
            self.data = yaml.safe_load(f)

    @property
    def server_port(self) -> int:
        return self.data['server']['port']

    @property
    def upload_dir(self) -> str:
        return self.data['server']['upload_dir']

    @property
    def gdb_base_port(self) -> int:
        return self.data['ports']['gdb_base']

    @property
    def telnet_base_port(self) -> int:
        return self.data['ports']['telnet_base']

    def get_probe(self, probe_id: int) -> Optional[Dict]:
        """Get probe configuration by ID"""
        for probe in self.data['probes']:
            if probe['id'] == probe_id:
                return probe
        return None

    def get_all_probes(self) -> List[Dict]:
        """Get all probe configurations"""
        return self.data['probes']

    def get_target(self, target_name: str) -> Optional[Dict]:
        """Get target configuration by name"""
        return self.data['targets'].get(target_name)

    def get_all_targets(self) -> Dict[str, Dict]:
        """Get all target configurations"""
        return self.data['targets']

    def get_container(self, container_key: str) -> Optional[Dict]:
        """Get container configuration by key"""
        return self.data['containers'].get(container_key)

    def get_all_containers(self) -> Dict[str, Dict]:
        """Get all container configurations"""
        return self.data['containers']

    def get_command(self, target_name: str, interface: str, mode: str) -> Optional[str]:
        """
        Get command template for a specific target, interface, and mode

        Args:
            target_name: Target device name (e.g., 'nrf52840')
            interface: Probe interface type (e.g., 'jlink', 'cmsis-dap')
            mode: Operation mode ('debug' or 'flash')

        Returns:
            Command template string or None if not found
        """
        target = self.get_target(target_name)
        if not target:
            return None

        commands = target.get('commands', {})
        interface_commands = commands.get(interface, {})
        return interface_commands.get(mode)

    def format_command(self, command_template: str, **kwargs) -> str:
        """
        Format command template with provided arguments

        Args:
            command_template: Command template string with {placeholders}
            **kwargs: Arguments to substitute in template

        Returns:
            Formatted command string
        """
        return command_template.format(**kwargs)

    def is_probe_compatible(self, target_name: str, probe_id: int) -> bool:
        """Check if a probe is compatible with a target"""
        target = self.get_target(target_name)
        if not target:
            return False

        probe = self.get_probe(probe_id)
        if not probe:
            return False

        probe_interface = probe.get('interface')
        compatible_probes = target.get('compatible_probes', [])
        return probe_interface in compatible_probes

    def get_container_for_target(self, target_name: str) -> Optional[str]:
        """Get the container name for a target"""
        target = self.get_target(target_name)
        if not target:
            return None

        container_key = target.get('container')
        container = self.get_container(container_key)
        if not container:
            return None

        return container['name']

# Singleton instance
_config_instance = None

def get_config(config_path: str = None) -> Config:
    """Get or create Config singleton instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance
