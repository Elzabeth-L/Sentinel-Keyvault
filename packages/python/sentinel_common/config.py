from functools import lru_cache

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    service_name: str = "sentinel-service"
    service_version: str = "0.1.0"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    entra_audience: str | None = None
    entra_authority_host: AnyHttpUrl = AnyHttpUrl("https://login.microsoftonline.com")
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_redirect_uri: str = "http://localhost:8080/auth/callback"
    frontend_url: str = "http://localhost:8080"
    session_cookie_name: str = "sentinel_session"
    session_cookie_domain: str | None = None
    session_cookie_secure: bool = False
    session_ttl_seconds: int = 28800
    session_signing_key: str | None = None
    token_encryption_key: str | None = None
    allowed_tenants: tuple[str, ...] = ()
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    audit_service_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8006")
    identity_service_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8001")
    internal_api_token: str | None = None
    azure_client_id: str | None = None
    azure_tenant_id: str | None = None
    azure_client_certificate_path: str | None = None
    bootstrap_tenant_id: str | None = None
    bootstrap_tenant_name: str = "Sentinel Development Tenant"
    bootstrap_admin_object_id: str | None = None
    bootstrap_admin_name: str = "Sentinel Administrator"
    relationship_service_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8003")
    login_blob_account_url: AnyHttpUrl | None = None
    login_blob_container_name: str = "sentinel-login-events"

    @field_validator("login_blob_account_url", mode="before")
    @classmethod
    def empty_url_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("allowed_tenants", "cors_origins", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
