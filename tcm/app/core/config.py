"""Application configuration loading for the TCM controller."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, validator


class MetadataConfig(BaseModel):
    id: str
    location: str
    timezone: str


class NetworkConfig(BaseModel):
    hostname: str
    ipv4: Dict[str, str]
    dns: List[str] = Field(default_factory=list)


class LoopConfig(BaseModel):
    fast_tick_seconds: float = Field(gt=0, default=0.25)
    logic_tick_seconds: float = Field(gt=0, default=60)
    flood_refresh_seconds: float = Field(gt=0, default=120)


class DHT11Config(BaseModel):
    enabled: bool = True
    battery_pin: int = 4
    cabinet_pin: int = 5


class DS18B20Config(BaseModel):
    enabled: bool = False
    bus_path: Path = Path("/sys/bus/w1/devices")
    ids: List[str] = Field(default_factory=list)


class BuzzerConfig(BaseModel):
    gpio_pin: int = 22


class SensorConfig(BaseModel):
    dht11: DHT11Config = Field(default_factory=DHT11Config)
    ds18b20: DS18B20Config = Field(default_factory=DS18B20Config)
    buzzer: BuzzerConfig = Field(default_factory=BuzzerConfig)


class ThresholdConfig(BaseModel):
    grzalka_c: float = 5.0
    klimatyzacja_c: float = 25.0
    went_c: float = 30.0
    histereza_c: float = 1.0


class InputPolarities(BaseModel):
    door_open_is_high: bool = True
    flood_active_is_low: bool = True
    dip_on_is_high: bool = True


class InputConfig(BaseModel):
    door_channels: List[str] = Field(default_factory=list)
    flood_channels: List[str] = Field(default_factory=list)
    polarities: InputPolarities = Field(default_factory=InputPolarities)
    anti_glitch_ms: int = Field(default=150, ge=0)
    anti_flap_seconds: float = Field(default=3.0, ge=0)


class OutputMap(BaseModel):
    active_low: bool = False
    map: Dict[str, List[str]] = Field(default_factory=dict)


class OutputConfig(BaseModel):
    relays: OutputMap = Field(default_factory=OutputMap)
    transistors: OutputMap = Field(default_factory=OutputMap)


class StrikeAssignment(BaseModel):
    transistor: Optional[str] = None

    @validator("transistor")
    def validate_transistor(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value not in {f"T{i}" for i in range(2, 9)}:
            raise ValueError("Strike transistor must be one of T2..T8")
        return value


class StrikeConfig(BaseModel):
    default_duration_seconds: float = Field(default=10.0, gt=0)
    assignments: Dict[str, StrikeAssignment] = Field(default_factory=dict)


class PanelConfig(BaseModel):
    enabled: bool = True
    require_dip_high: bool = False


class UIPanelsConfig(BaseModel):
    operator: PanelConfig = Field(default_factory=PanelConfig)
    technik: PanelConfig = Field(default_factory=PanelConfig)
    serwis: PanelConfig = Field(default_factory=PanelConfig)


class UIDashboardConfig(BaseModel):
    show_outputs: List[str] = Field(default_factory=list)


class UIConfig(BaseModel):
    panels: UIPanelsConfig = Field(default_factory=UIPanelsConfig)
    dashboard: UIDashboardConfig = Field(default_factory=UIDashboardConfig)


class LoggingConfig(BaseModel):
    sqlite_path: Path = Path("/var/lib/tcm/events.db")
    retention_days: int = 365
    encrypted_fields: List[str] = Field(default_factory=list)
    export_chunk_size: int = 500


class SecretRefs(BaseModel):
    secret_key_file: Path
    fernet_key_file: Path
    admin_hash_file: Path


class AppConfig(BaseModel):
    metadata: MetadataConfig
    network: NetworkConfig
    loops: LoopConfig = Field(default_factory=LoopConfig)
    sensors: SensorConfig = Field(default_factory=SensorConfig)
    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)
    inputs: InputConfig = Field(default_factory=InputConfig)
    outputs: OutputConfig = Field(default_factory=OutputConfig)
    strike: StrikeConfig = Field(default_factory=StrikeConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    secrets: SecretRefs

    @classmethod
    def from_yaml(cls, path: Path) -> "AppConfig":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.parse_obj(data)


def load_secret_file(path: Path) -> Optional[str]:
    """Read a secret from a file, returning ``None`` if the file is missing."""

    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None


def deep_update(original: Dict[str, Any], new_values: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively update ``original`` with ``new_values`` returning a new dict."""

    result: Dict[str, Any] = json.loads(json.dumps(original))
    for key, value in new_values.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_update(result[key], value)
        else:
            result[key] = value
    return result

