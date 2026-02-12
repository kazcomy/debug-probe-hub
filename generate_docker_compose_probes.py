#!/usr/bin/env python3
"""
Generate docker-compose.probes.yml from config.yml.

Goal: one container instance per (toolchain container) x (probe_id).
This isolates process cleanup and commercial tools that can't run concurrently
in a shared container, while still reusing the same image.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import yaml


def build_service(
    base_container_name: str,
    image_name: str,
    build_context: str,
    probe_id: int,
    include_build: bool,
) -> Dict[str, Any]:
    instance_name = f"{base_container_name}-p{probe_id}"
    service: Dict[str, Any] = {
        "image": f"{image_name}:latest",
        "container_name": instance_name,
        "privileged": True,
        "volumes": [
            "/dev:/dev",
            "/tmp/flash_staging:/work",
            "./config.yml:/config.yml:ro",
        ],
        "command": "sleep infinity",
        "network_mode": "host",
        "restart": "unless-stopped",
    }
    if include_build:
        service["build"] = {"context": build_context, "dockerfile": "Dockerfile"}
    return service


def load_override_build_settings(override_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load docker-compose override build settings by service name."""
    if not override_path.exists():
        return {}

    raw = yaml.safe_load(override_path.read_text()) or {}
    services = raw.get("services", {})
    build_settings: Dict[str, Dict[str, Any]] = {}

    for service_name, service_def in services.items():
        build_cfg = service_def.get("build")
        if isinstance(build_cfg, dict):
            build_settings[service_name] = build_cfg

    return build_settings


def merge_build_config(
    generated_build: Dict[str, Any], override_build: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge override build config while preserving generated context/dockerfile defaults."""
    merged = dict(generated_build)

    for key, value in override_build.items():
        if key == "args":
            base_args = merged.get("args", {})
            merged["args"] = {**base_args, **value}
        else:
            merged[key] = value

    return merged


def generate(config_path: Path, override_path: Path) -> Dict[str, Any]:
    config = yaml.safe_load(config_path.read_text())

    containers = config.get("containers", {})
    probes = config.get("probes", [])
    override_builds = load_override_build_settings(override_path)

    probe_ids = []
    for probe in probes:
        probe_id = int(probe["id"])
        probe_ids.append(probe_id)

    services: Dict[str, Any] = {}
    for container_key, container in containers.items():
        _ = container_key
        base_container_name = container["name"]
        image_name = container["image_name"]
        build_context = container["build_context"]

        # Only one instance per toolchain includes `build:` to avoid redundant builds.
        # Other instances reuse the same `image:` tag.
        for i, probe_id in enumerate(probe_ids):
            service_name = f"{base_container_name}-p{probe_id}"
            service = build_service(
                base_container_name=base_container_name,
                image_name=image_name,
                build_context=build_context,
                probe_id=probe_id,
                include_build=(i == 0),
            )
            if i == 0 and "build" in service:
                # Apply override settings from either:
                # 1) base service name (e.g. debug-box-wch), or
                # 2) generated service name (e.g. debug-box-wch-p1)
                override_build = (
                    override_builds.get(base_container_name)
                    or override_builds.get(service_name)
                )
                if override_build:
                    service["build"] = merge_build_config(service["build"], override_build)

            services[service_name] = service

    return {"version": "3.8", "services": services}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml", help="Path to config.yml")
    parser.add_argument(
        "--output",
        default="docker-compose.probes.yml",
        help="Output compose file path",
    )
    parser.add_argument(
        "--override",
        default="docker-compose.override.yml",
        help="Optional override compose file to merge build args from",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    out_path = Path(args.output)
    override_path = Path(args.override)

    compose = generate(config_path, override_path)
    out_path.write_text(yaml.safe_dump(compose, sort_keys=False))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
