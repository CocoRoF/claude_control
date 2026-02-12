"""
Config management module for Claude Control.

This module provides:
- BaseConfig: Abstract base class for all configurations
- ConfigManager: Manages loading, saving, and auto-registration of configs
- Channel configs: Discord, Slack, Teams configurations
"""

from .base import BaseConfig, ConfigField
from .manager import ConfigManager, get_config_manager
from .channel_configs import DiscordConfig, SlackConfig, TeamsConfig

__all__ = [
    'BaseConfig',
    'ConfigField',
    'ConfigManager',
    'get_config_manager',
    'DiscordConfig',
    'SlackConfig',
    'TeamsConfig'
]
