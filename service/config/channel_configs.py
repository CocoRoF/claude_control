"""
Multi-channel configuration classes for Claude Control.

Provides configuration for:
- Discord: Bot integration for Discord servers
- Slack: Bot integration for Slack workspaces
- Teams: Bot integration for Microsoft Teams
"""

from dataclasses import dataclass, field
from typing import List

from .base import BaseConfig, ConfigField, FieldType, register_config


@register_config
@dataclass
class DiscordConfig(BaseConfig):
    """
    Discord Bot Configuration.

    Enables Claude Control integration with Discord servers.
    Allows users to interact with Claude sessions via Discord messages.
    """

    # Connection settings
    enabled: bool = False
    bot_token: str = ""
    application_id: str = ""

    # Server/Guild settings
    guild_ids: List[str] = field(default_factory=list)  # Specific guilds, empty = all

    # Channel settings
    allowed_channel_ids: List[str] = field(default_factory=list)  # Empty = all channels
    command_prefix: str = "!"

    # Permissions
    admin_role_ids: List[str] = field(default_factory=list)
    allowed_user_ids: List[str] = field(default_factory=list)  # Empty = all users

    # Behavior settings
    respond_to_mentions: bool = True
    respond_to_dms: bool = False
    auto_thread: bool = True  # Create threads for conversations
    max_message_length: int = 2000

    # Session settings
    session_timeout_minutes: int = 30  # Auto-close inactive sessions
    max_sessions_per_user: int = 3
    default_prompt: str = ""  # Default system prompt for Discord sessions

    @classmethod
    def get_config_name(cls) -> str:
        return "discord"

    @classmethod
    def get_display_name(cls) -> str:
        return "Discord"

    @classmethod
    def get_description(cls) -> str:
        return "Configure Discord bot integration for Claude Control. Allows users to interact with Claude sessions through Discord messages."

    @classmethod
    def get_category(cls) -> str:
        return "channels"

    @classmethod
    def get_icon(cls) -> str:
        return "discord"

    @classmethod
    def get_fields_metadata(cls) -> List[ConfigField]:
        return [
            # Connection group
            ConfigField(
                name="enabled",
                field_type=FieldType.BOOLEAN,
                label="Enable Discord Integration",
                description="Enable or disable Discord bot integration",
                default=False,
                group="connection"
            ),
            ConfigField(
                name="bot_token",
                field_type=FieldType.PASSWORD,
                label="Bot Token",
                description="Discord bot token from Discord Developer Portal",
                required=True,
                placeholder="Enter your Discord bot token",
                group="connection"
            ),
            ConfigField(
                name="application_id",
                field_type=FieldType.STRING,
                label="Application ID",
                description="Discord application ID from Developer Portal",
                placeholder="123456789012345678",
                group="connection"
            ),

            # Server group
            ConfigField(
                name="guild_ids",
                field_type=FieldType.TEXTAREA,
                label="Guild IDs (Optional)",
                description="Comma-separated list of guild/server IDs. Leave empty for all guilds.",
                placeholder="123456789012345678, 987654321098765432",
                group="server"
            ),
            ConfigField(
                name="allowed_channel_ids",
                field_type=FieldType.TEXTAREA,
                label="Allowed Channel IDs (Optional)",
                description="Comma-separated list of channel IDs where bot responds. Leave empty for all channels.",
                placeholder="123456789012345678, 987654321098765432",
                group="server"
            ),
            ConfigField(
                name="command_prefix",
                field_type=FieldType.STRING,
                label="Command Prefix",
                description="Prefix for bot commands (e.g., !claude, /ask)",
                default="!",
                placeholder="!",
                group="server"
            ),

            # Permissions group
            ConfigField(
                name="admin_role_ids",
                field_type=FieldType.TEXTAREA,
                label="Admin Role IDs",
                description="Comma-separated list of role IDs with admin privileges",
                placeholder="123456789012345678",
                group="permissions"
            ),
            ConfigField(
                name="allowed_user_ids",
                field_type=FieldType.TEXTAREA,
                label="Allowed User IDs (Optional)",
                description="Comma-separated list of user IDs allowed to use the bot. Leave empty for all users.",
                placeholder="123456789012345678, 987654321098765432",
                group="permissions"
            ),

            # Behavior group
            ConfigField(
                name="respond_to_mentions",
                field_type=FieldType.BOOLEAN,
                label="Respond to Mentions",
                description="Respond when the bot is mentioned in a message",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="respond_to_dms",
                field_type=FieldType.BOOLEAN,
                label="Respond to Direct Messages",
                description="Allow users to interact via DMs",
                default=False,
                group="behavior"
            ),
            ConfigField(
                name="auto_thread",
                field_type=FieldType.BOOLEAN,
                label="Auto Create Threads",
                description="Automatically create threads for conversations",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="max_message_length",
                field_type=FieldType.NUMBER,
                label="Max Message Length",
                description="Maximum characters per message (Discord limit: 2000)",
                default=2000,
                min_value=100,
                max_value=2000,
                group="behavior"
            ),

            # Session group
            ConfigField(
                name="session_timeout_minutes",
                field_type=FieldType.NUMBER,
                label="Session Timeout (minutes)",
                description="Auto-close inactive sessions after this many minutes",
                default=30,
                min_value=5,
                max_value=1440,
                group="session"
            ),
            ConfigField(
                name="max_sessions_per_user",
                field_type=FieldType.NUMBER,
                label="Max Sessions Per User",
                description="Maximum concurrent sessions per user",
                default=3,
                min_value=1,
                max_value=10,
                group="session"
            ),
            ConfigField(
                name="default_prompt",
                field_type=FieldType.TEXTAREA,
                label="Default System Prompt",
                description="Default system prompt for Discord-initiated sessions",
                placeholder="You are a helpful assistant...",
                group="session"
            ),
        ]


@register_config
@dataclass
class SlackConfig(BaseConfig):
    """
    Slack Bot Configuration.

    Enables Claude Control integration with Slack workspaces.
    Allows users to interact with Claude sessions via Slack messages.
    """

    # Connection settings
    enabled: bool = False
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-... for Socket Mode
    signing_secret: str = ""

    # Workspace settings
    workspace_id: str = ""

    # Channel settings
    allowed_channel_ids: List[str] = field(default_factory=list)
    default_channel_id: str = ""

    # Permissions
    admin_user_ids: List[str] = field(default_factory=list)
    allowed_user_ids: List[str] = field(default_factory=list)

    # Behavior settings
    respond_to_mentions: bool = True
    respond_to_dms: bool = True
    respond_in_thread: bool = True  # Reply in threads
    use_blocks: bool = True  # Use Slack Block Kit for rich formatting
    max_message_length: int = 4000

    # Session settings
    session_timeout_minutes: int = 30
    max_sessions_per_user: int = 3
    default_prompt: str = ""

    # Slash commands
    enable_slash_commands: bool = True
    slash_command_name: str = "/claude"

    @classmethod
    def get_config_name(cls) -> str:
        return "slack"

    @classmethod
    def get_display_name(cls) -> str:
        return "Slack"

    @classmethod
    def get_description(cls) -> str:
        return "Configure Slack bot integration for Claude Control. Allows users to interact with Claude sessions through Slack messages and slash commands."

    @classmethod
    def get_category(cls) -> str:
        return "channels"

    @classmethod
    def get_icon(cls) -> str:
        return "slack"

    @classmethod
    def get_fields_metadata(cls) -> List[ConfigField]:
        return [
            # Connection group
            ConfigField(
                name="enabled",
                field_type=FieldType.BOOLEAN,
                label="Enable Slack Integration",
                description="Enable or disable Slack bot integration",
                default=False,
                group="connection"
            ),
            ConfigField(
                name="bot_token",
                field_type=FieldType.PASSWORD,
                label="Bot Token (xoxb-)",
                description="Slack bot token starting with xoxb-",
                required=True,
                placeholder="xoxb-...",
                group="connection"
            ),
            ConfigField(
                name="app_token",
                field_type=FieldType.PASSWORD,
                label="App Token (xapp-)",
                description="Slack app-level token for Socket Mode (starts with xapp-)",
                placeholder="xapp-...",
                group="connection"
            ),
            ConfigField(
                name="signing_secret",
                field_type=FieldType.PASSWORD,
                label="Signing Secret",
                description="Slack app signing secret for request verification",
                placeholder="Enter signing secret",
                group="connection"
            ),

            # Workspace group
            ConfigField(
                name="workspace_id",
                field_type=FieldType.STRING,
                label="Workspace ID",
                description="Slack workspace ID (optional)",
                placeholder="T01234567",
                group="workspace"
            ),
            ConfigField(
                name="allowed_channel_ids",
                field_type=FieldType.TEXTAREA,
                label="Allowed Channel IDs",
                description="Comma-separated list of channel IDs. Leave empty for all channels.",
                placeholder="C01234567, C98765432",
                group="workspace"
            ),
            ConfigField(
                name="default_channel_id",
                field_type=FieldType.STRING,
                label="Default Channel ID",
                description="Default channel for bot responses",
                placeholder="C01234567",
                group="workspace"
            ),

            # Permissions group
            ConfigField(
                name="admin_user_ids",
                field_type=FieldType.TEXTAREA,
                label="Admin User IDs",
                description="Comma-separated list of user IDs with admin privileges",
                placeholder="U01234567",
                group="permissions"
            ),
            ConfigField(
                name="allowed_user_ids",
                field_type=FieldType.TEXTAREA,
                label="Allowed User IDs",
                description="Comma-separated list of user IDs allowed to use the bot. Leave empty for all users.",
                placeholder="U01234567, U98765432",
                group="permissions"
            ),

            # Behavior group
            ConfigField(
                name="respond_to_mentions",
                field_type=FieldType.BOOLEAN,
                label="Respond to Mentions",
                description="Respond when the bot is mentioned",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="respond_to_dms",
                field_type=FieldType.BOOLEAN,
                label="Respond to Direct Messages",
                description="Allow users to interact via DMs",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="respond_in_thread",
                field_type=FieldType.BOOLEAN,
                label="Reply in Threads",
                description="Reply to messages in threads",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="use_blocks",
                field_type=FieldType.BOOLEAN,
                label="Use Block Kit",
                description="Use Slack Block Kit for rich message formatting",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="max_message_length",
                field_type=FieldType.NUMBER,
                label="Max Message Length",
                description="Maximum characters per message (Slack limit: 4000)",
                default=4000,
                min_value=100,
                max_value=4000,
                group="behavior"
            ),

            # Session group
            ConfigField(
                name="session_timeout_minutes",
                field_type=FieldType.NUMBER,
                label="Session Timeout (minutes)",
                description="Auto-close inactive sessions after this many minutes",
                default=30,
                min_value=5,
                max_value=1440,
                group="session"
            ),
            ConfigField(
                name="max_sessions_per_user",
                field_type=FieldType.NUMBER,
                label="Max Sessions Per User",
                description="Maximum concurrent sessions per user",
                default=3,
                min_value=1,
                max_value=10,
                group="session"
            ),
            ConfigField(
                name="default_prompt",
                field_type=FieldType.TEXTAREA,
                label="Default System Prompt",
                description="Default system prompt for Slack-initiated sessions",
                placeholder="You are a helpful assistant...",
                group="session"
            ),

            # Slash commands group
            ConfigField(
                name="enable_slash_commands",
                field_type=FieldType.BOOLEAN,
                label="Enable Slash Commands",
                description="Enable slash command support",
                default=True,
                group="commands"
            ),
            ConfigField(
                name="slash_command_name",
                field_type=FieldType.STRING,
                label="Slash Command Name",
                description="Name of the slash command (e.g., /claude)",
                default="/claude",
                placeholder="/claude",
                group="commands"
            ),
        ]


@register_config
@dataclass
class TeamsConfig(BaseConfig):
    """
    Microsoft Teams Bot Configuration.

    Enables Claude Control integration with Microsoft Teams.
    Allows users to interact with Claude sessions via Teams messages.
    """

    # Connection settings
    enabled: bool = False
    app_id: str = ""  # Microsoft App ID
    app_password: str = ""  # Microsoft App Password
    tenant_id: str = ""  # Azure AD tenant ID (optional, for single-tenant)

    # Bot Framework settings
    bot_endpoint: str = ""  # Messaging endpoint URL

    # Channel settings
    allowed_team_ids: List[str] = field(default_factory=list)
    allowed_channel_ids: List[str] = field(default_factory=list)

    # Permissions
    admin_user_ids: List[str] = field(default_factory=list)  # Azure AD Object IDs
    allowed_user_ids: List[str] = field(default_factory=list)

    # Behavior settings
    respond_to_mentions: bool = True
    respond_to_direct_messages: bool = True
    respond_in_threads: bool = True
    use_adaptive_cards: bool = True  # Use Adaptive Cards for rich formatting
    max_message_length: int = 28000  # Teams limit

    # Session settings
    session_timeout_minutes: int = 30
    max_sessions_per_user: int = 3
    default_prompt: str = ""

    # Graph API settings (optional, for advanced features)
    enable_graph_api: bool = False
    graph_client_secret: str = ""

    @classmethod
    def get_config_name(cls) -> str:
        return "teams"

    @classmethod
    def get_display_name(cls) -> str:
        return "Microsoft Teams"

    @classmethod
    def get_description(cls) -> str:
        return "Configure Microsoft Teams bot integration for Claude Control. Allows users to interact with Claude sessions through Teams messages."

    @classmethod
    def get_category(cls) -> str:
        return "channels"

    @classmethod
    def get_icon(cls) -> str:
        return "teams"

    @classmethod
    def get_fields_metadata(cls) -> List[ConfigField]:
        return [
            # Connection group
            ConfigField(
                name="enabled",
                field_type=FieldType.BOOLEAN,
                label="Enable Teams Integration",
                description="Enable or disable Microsoft Teams bot integration",
                default=False,
                group="connection"
            ),
            ConfigField(
                name="app_id",
                field_type=FieldType.STRING,
                label="Microsoft App ID",
                description="Application (client) ID from Azure Portal",
                required=True,
                placeholder="00000000-0000-0000-0000-000000000000",
                group="connection"
            ),
            ConfigField(
                name="app_password",
                field_type=FieldType.PASSWORD,
                label="App Password",
                description="Client secret from Azure Portal",
                required=True,
                placeholder="Enter app password/secret",
                group="connection"
            ),
            ConfigField(
                name="tenant_id",
                field_type=FieldType.STRING,
                label="Tenant ID (Optional)",
                description="Azure AD Tenant ID for single-tenant apps. Leave empty for multi-tenant.",
                placeholder="00000000-0000-0000-0000-000000000000",
                group="connection"
            ),
            ConfigField(
                name="bot_endpoint",
                field_type=FieldType.URL,
                label="Bot Endpoint URL",
                description="The messaging endpoint URL for your bot",
                placeholder="https://your-bot.azurewebsites.net/api/messages",
                group="connection"
            ),

            # Team settings group
            ConfigField(
                name="allowed_team_ids",
                field_type=FieldType.TEXTAREA,
                label="Allowed Team IDs",
                description="Comma-separated list of Team IDs. Leave empty for all teams.",
                placeholder="19:abc123...",
                group="teams"
            ),
            ConfigField(
                name="allowed_channel_ids",
                field_type=FieldType.TEXTAREA,
                label="Allowed Channel IDs",
                description="Comma-separated list of channel IDs. Leave empty for all channels.",
                placeholder="19:abc123...",
                group="teams"
            ),

            # Permissions group
            ConfigField(
                name="admin_user_ids",
                field_type=FieldType.TEXTAREA,
                label="Admin User IDs (Azure AD Object IDs)",
                description="Comma-separated list of Azure AD Object IDs with admin privileges",
                placeholder="00000000-0000-0000-0000-000000000000",
                group="permissions"
            ),
            ConfigField(
                name="allowed_user_ids",
                field_type=FieldType.TEXTAREA,
                label="Allowed User IDs",
                description="Comma-separated list of user IDs allowed to use the bot. Leave empty for all.",
                placeholder="00000000-0000-0000-0000-000000000000",
                group="permissions"
            ),

            # Behavior group
            ConfigField(
                name="respond_to_mentions",
                field_type=FieldType.BOOLEAN,
                label="Respond to Mentions",
                description="Respond when the bot is mentioned",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="respond_to_direct_messages",
                field_type=FieldType.BOOLEAN,
                label="Respond to Direct Messages",
                description="Allow users to interact via 1:1 chat",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="respond_in_threads",
                field_type=FieldType.BOOLEAN,
                label="Reply in Threads",
                description="Reply to messages in threads/conversations",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="use_adaptive_cards",
                field_type=FieldType.BOOLEAN,
                label="Use Adaptive Cards",
                description="Use Adaptive Cards for rich message formatting",
                default=True,
                group="behavior"
            ),
            ConfigField(
                name="max_message_length",
                field_type=FieldType.NUMBER,
                label="Max Message Length",
                description="Maximum characters per message",
                default=28000,
                min_value=100,
                max_value=28000,
                group="behavior"
            ),

            # Session group
            ConfigField(
                name="session_timeout_minutes",
                field_type=FieldType.NUMBER,
                label="Session Timeout (minutes)",
                description="Auto-close inactive sessions after this many minutes",
                default=30,
                min_value=5,
                max_value=1440,
                group="session"
            ),
            ConfigField(
                name="max_sessions_per_user",
                field_type=FieldType.NUMBER,
                label="Max Sessions Per User",
                description="Maximum concurrent sessions per user",
                default=3,
                min_value=1,
                max_value=10,
                group="session"
            ),
            ConfigField(
                name="default_prompt",
                field_type=FieldType.TEXTAREA,
                label="Default System Prompt",
                description="Default system prompt for Teams-initiated sessions",
                placeholder="You are a helpful assistant...",
                group="session"
            ),

            # Graph API group
            ConfigField(
                name="enable_graph_api",
                field_type=FieldType.BOOLEAN,
                label="Enable Microsoft Graph API",
                description="Enable Graph API for advanced features (user info, files, etc.)",
                default=False,
                group="graph"
            ),
            ConfigField(
                name="graph_client_secret",
                field_type=FieldType.PASSWORD,
                label="Graph API Client Secret",
                description="Additional client secret for Graph API access (if different)",
                placeholder="Enter Graph API secret",
                group="graph"
            ),
        ]
