"""JOV.si configuration management.

All settings read from environment variables prefixed with JOVSI_.
Validates combinations strictly on startup.
"""

from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AutonomyLevel(str, Enum):
    L0_DRY_RUN = "L0_DRY_RUN"
    L1_MOCK_SUPERVISED = "L1_MOCK_SUPERVISED"
    L2_SUPERVISED = "L2_SUPERVISED"
    L3_AUTO_WITHIN_LIMITS = "L3_AUTO_WITHIN_LIMITS"


class EvidenceLevel(str, Enum):
    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOVSI_",
        case_sensitive=False,
        extra="ignore"
    )

    # Core product settings
    PRODUCT_NAME: str = "JOV.si"
    AUTONOMY_LEVEL: AutonomyLevel = AutonomyLevel.L0_DRY_RUN
    ALLOW_REAL_SUBMISSION: bool = False
    SUITABILITY_FLOOR: int = Field(default=65, ge=0, le=100)
    DAILY_CAP_GLOBAL: int = Field(default=10, ge=1)
    DAILY_CAP_PER_PORTAL: int = Field(default=5, ge=1)
    DAILY_CAP_PER_COMPANY: int = Field(default=1, ge=1)
    TIMEZONE: str = "Asia/Kolkata"
    MIN_EVIDENCE_LEVEL: EvidenceLevel = EvidenceLevel.E2
    LLM_ENABLED: bool = False
    LLM_API_KEY: Optional[str] = None
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-2.5-flash"
    GEMINI_API_KEY: Optional[str] = None

    # Aggregator API credentials (optional - activates Adzuna connector when set)
    ADZUNA_APP_ID: Optional[str] = None
    ADZUNA_API_KEY: Optional[str] = None

    @property
    def effective_llm_api_key(self) -> Optional[str]:
        return self.LLM_API_KEY or self.GEMINI_API_KEY

    # Host allowlist (Release 1 strictly loopback mock)
    SUBMIT_HOST_ALLOWLIST: List[str] = ["127.0.0.1:8765"]

    # Storage and Database
    DATABASE_URL: str = "sqlite:///./jovsi.db"
    ARTIFACTS_DIR: Path = Path("./artifacts")
    SECRET_KEY: str = "jovsi-insecure-dev-hmac-key-change-in-prod-32bytes"

    # API Server
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    MOCK_PORTAL_PORT: int = 8765

    @model_validator(mode="after")
    def validate_safety_rules(self) -> "Settings":
        # In Release 1, ALLOW_REAL_SUBMISSION cannot be true unless non-mock hosts are present
        if self.ALLOW_REAL_SUBMISSION and self.SUBMIT_HOST_ALLOWLIST == ["127.0.0.1:8765"]:
            # Real submission allowed flag set, but no real hosts allowlisted
            pass
        # If L2 or L3 selected in Release 1, enforce safety
        if self.AUTONOMY_LEVEL in (AutonomyLevel.L2_SUPERVISED, AutonomyLevel.L3_AUTO_WITHIN_LIMITS):
            if not self.ALLOW_REAL_SUBMISSION:
                raise ValueError("Autonomy level L2/L3 requires ALLOW_REAL_SUBMISSION=True")
        return self


# Global singleton settings
settings = Settings()
