from functools import lru_cache
from typing import List

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Self-Learning Vision API"
    auth_enabled: bool = False
    auth_dev_email: str = "local-user@self-learning-vision.local"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/self_learning_vision"
    storage_dir: str = "./data/uploads"
    cors_origins: str = "http://localhost:3000"

    jwt_secret: str = "change_me_before_public_deployments"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 120

    enable_face_matching: bool = True
    embedding_provider: str = "auto"
    paid_provider_enabled: bool = False
    paid_provider_api_key: str = ""
    provider_plugin_dirs: str = ""
    privacy_local_only_mode: bool = True
    privacy_allow_hosted_providers: bool = False
    face_quality_min_threshold: float = 0.40
    face_quality_hard_fail_threshold: float = 0.20
    recognition_top_k: int = 3
    recognition_accept_threshold: float = 0.72
    recognition_tentative_threshold: float = 0.50
    recognition_calibration_mode: str = "linear"
    recognition_cross_provider_bonus: float = 0.06
    recognition_disagreement_penalty: float = 0.12
    unknown_cluster_similarity_threshold: float = 0.88
    unknown_cluster_familiarity_min_samples: int = 2

    model_config = ConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
