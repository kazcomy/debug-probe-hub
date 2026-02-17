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

    @property
    def rtt_base_port(self) -> int:
        return self.data['ports']['rtt_base']

    def get_probe(self, probe_id: int) -> Optional[Dict]:
        """Get probe configuration by ID"""
        for probe in self.data['probes']:
            if probe['id'] == probe_id:
                return probe
        return None

    def get_all_probes(self) -> List[Dict]:
        """Get all probe configurations"""
        return self.data['probes']

    def get_probe_device_path(self, probe_id: int) -> Optional[str]:
        """Get device_path for USB-serial probes"""
        probe = self.get_probe(probe_id)
        if not probe:
            return None
        return probe.get('device_path')

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

    def get_transport_config(self, target_name: str, interface: str) -> Dict:
        """Get transport policy for target/interface pair."""
        target = self.get_target(target_name)
        if not target:
            return {}

        transports = target.get('transports', {})
        if not isinstance(transports, dict):
            return {}

        cfg = transports.get(interface, {})
        if isinstance(cfg, str):
            normalized = cfg.strip().lower()
            if not normalized:
                return {}
            return {"default": normalized, "allowed": [normalized]}

        if not isinstance(cfg, dict):
            return {}

        default_transport = cfg.get("default")
        if isinstance(default_transport, str):
            default_transport = default_transport.strip().lower()
        else:
            default_transport = None

        allowed = []
        raw_allowed = cfg.get("allowed", [])
        if isinstance(raw_allowed, list):
            for t in raw_allowed:
                if isinstance(t, str):
                    normalized = t.strip().lower()
                    if normalized:
                        allowed.append(normalized)

        if default_transport and default_transport not in allowed:
            allowed.insert(0, default_transport)

        return {
            "default": default_transport,
            "allowed": allowed,
        }

    def get_allowed_transports(self, target_name: str, interface: str) -> List[str]:
        """Get allowed transports for target/interface pair."""
        cfg = self.get_transport_config(target_name, interface)
        return cfg.get("allowed", [])

    def get_default_transport(self, target_name: str, interface: str) -> Optional[str]:
        """Get default transport for target/interface pair."""
        cfg = self.get_transport_config(target_name, interface)
        default_transport = cfg.get("default")
        if default_transport:
            return default_transport

        allowed = cfg.get("allowed", [])
        if allowed:
            return allowed[0]
        return None

    def _normalize_usb_id(self, value) -> str:
        """Normalize USB ID strings such as '0x8010' or '8010'."""
        if value is None:
            return ""
        normalized = str(value).strip().lower()
        if normalized.startswith("0x"):
            normalized = normalized[2:]
        return normalized

    def get_wch_link_mode(self, probe: Optional[Dict]) -> Optional[str]:
        """
        Infer WCH-Link mode from USB product ID.

        - 0x8010: RISC-V mode
        - 0x8012: ARM mode
        """
        if not isinstance(probe, dict):
            return None
        if probe.get("interface") != "wch-link":
            return None

        product_id = self._normalize_usb_id(probe.get("product_id"))
        if product_id == "8010":
            return "riscv"
        if product_id == "8012":
            return "arm"
        return None

    def validate_probe_transport(
        self,
        target_name: str,
        interface: str,
        probe: Optional[Dict],
        requested_transport: Optional[str],
        resolved_transport: Optional[str],
        mode: Optional[str] = None,
    ) -> None:
        """
        Validate transport against probe hardware mode restrictions.

        Raises:
            ValueError: if requested/resolved transport conflicts with probe mode.
        """
        if mode == "print":
            return

        if interface != "wch-link":
            return

        wch_mode = self.get_wch_link_mode(probe)
        requested = None
        if isinstance(requested_transport, str):
            requested = requested_transport.strip().lower() or None

        resolved = None
        if isinstance(resolved_transport, str):
            resolved = resolved_transport.strip().lower() or None

        probe_id = probe.get("id") if isinstance(probe, dict) else "unknown"
        product_id = self._normalize_usb_id(probe.get("product_id") if isinstance(probe, dict) else "")

        if wch_mode == "riscv":
            if requested and requested != "sdi":
                raise ValueError(
                    f"Transport '{requested}' is invalid for target={target_name}, "
                    f"interface={interface}: WCH-Link probe {probe_id} is in RISC-V mode "
                    f"(USB PID {product_id}), so transport is fixed to 'sdi'. "
                    f"Use '--transport sdi' or omit '--transport'. "
                    f"To use SWD/JTAG, switch the probe to ARM mode (USB PID 8012)."
                )
            if resolved and resolved != "sdi":
                raise ValueError(
                    f"Transport policy mismatch for target={target_name}, interface={interface}: "
                    f"WCH-Link probe {probe_id} is in RISC-V mode (USB PID {product_id}) and "
                    f"requires 'sdi', but resolved transport is '{resolved}'. "
                    f"Set targets.{target_name}.transports.{interface} to default/allowed 'sdi'."
                )
            return

        if wch_mode == "arm":
            if requested == "sdi":
                raise ValueError(
                    f"Transport '{requested}' is invalid for target={target_name}, "
                    f"interface={interface}: WCH-Link probe {probe_id} is in ARM mode "
                    f"(USB PID {product_id}), so choose 'swd' or 'jtag'."
                )

    def resolve_transport(
        self,
        target_name: str,
        interface: str,
        requested_transport: Optional[str],
        mode: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolve transport from user request and target policy.

        Raises:
            ValueError: If requested transport is not allowed.
        """
        if mode == "print":
            return None

        requested = None
        if isinstance(requested_transport, str):
            requested = requested_transport.strip().lower() or None

        allowed = self.get_allowed_transports(target_name, interface)
        default_transport = self.get_default_transport(target_name, interface)

        if requested:
            if not allowed:
                raise ValueError(
                    f"Transport '{requested}' was requested for target={target_name}, "
                    f"interface={interface}, but no transport policy is configured."
                )
            if requested not in allowed:
                if interface == "wch-link" and allowed == ["sdi"]:
                    raise ValueError(
                        f"Transport '{requested}' is invalid for target={target_name}, "
                        f"interface={interface}: this WCH RISC-V target is fixed to 'sdi'. "
                        f"Use '--transport sdi' or omit '--transport'. "
                        f"For SWD/JTAG, switch the probe to ARM mode (USB PID 8012) "
                        f"and use an ARM target policy."
                    )
                raise ValueError(
                    f"Transport '{requested}' is not allowed for target={target_name}, "
                    f"interface={interface}. Allowed: {allowed}"
                )
            return requested

        if default_transport:
            return default_transport
        return None

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

    def get_container_for_target(self, target_name: str, interface: str = None) -> Optional[str]:
        """Get the container name for a target (optionally resolved per interface)."""
        target = self.get_target(target_name)
        if not target:
            return None

        container_key = target.get('container')
        if isinstance(container_key, dict):
            if interface is None:
                return None
            container_key = container_key.get(interface)

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
