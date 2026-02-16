"""
Config management module for Claude Control.

This module provides:
- BaseConfig: Abstract base class for all configurations
- ConfigManager: Manages loading, saving, and auto-registration of configs
- Sub-config auto-discovery: Configs are organized under sub_config/<category>/

See sub_config/README.md for the config file organization policy.
"""

from .base import BaseConfig, ConfigField
from .manager import ConfigManager, get_config_manager

# Auto-discover all configs in sub_config/ subdirectories.
# This import triggers the discovery mechanism which walks through
# sub_config/<category>/*_config.py and registers each @register_config class.
from . import sub_config  # noqa: F401

# Re-export individual configs for backward compatibility
from .sub_config.channels.discord_config import DiscordConfig
from .sub_config.channels.slack_config import SlackConfig
from .sub_config.channels.teams_config import TeamsConfig

__all__ = [
    'BaseConfig',
    'ConfigField',
    'ConfigManager',
    'get_config_manager',
    'DiscordConfig',
    'SlackConfig',
    'TeamsConfig'
]
