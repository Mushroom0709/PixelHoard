"""OBS 客户端单例。"""
from obs import ObsClient

from config import settings


def _build_client() -> ObsClient:
    return ObsClient(
        access_key_id=settings.OBS_AK,
        secret_access_key=settings.OBS_SK,
        server=settings.OBS_ENDPOINT,
    )


obs = _build_client()


def obs_key(share_id: int, sub: str, filename: str) -> str:
    """统一构造 OBS key。

    例: obs_key(42, "raw", "img.jpg") -> "PixelHoard/shares/42/raw/img.jpg"
    """
    return f"{settings.OBS_WORKDIR}/shares/{share_id}/{sub}/{filename}"