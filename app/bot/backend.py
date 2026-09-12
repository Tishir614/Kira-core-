from __future__ import annotations
from pathlib import Path
import httpx


class BackendClient:
    def __init__(self, base_url: str, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def headers(self, user_id: int) -> dict[str, str]:
        return {"X-Telegram-User-Id": str(user_id)}

    async def create_project(self, user_id: int, name: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/projects", headers=self.headers(user_id), json={"name": name})
        response.raise_for_status()
        return response.json()["id"]

    async def upload(self, user_id: int, project_id: str, path: Path, mime: str, category: str = "reference") -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with path.open("rb") as source:
                response = await client.post(
                    f"{self.base_url}/projects/{project_id}/uploads",
                    headers=self.headers(user_id),
                    data={"category": category},
                    files={"upload": (path.name, source, mime)},
                )
        response.raise_for_status()
        return response.json()

    async def reconstruct(self, user_id: int, project_id: str, prompt: str, quality: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/projects/{project_id}/image-to-3d", headers=self.headers(user_id), json={"prompt": prompt, "quality": quality}
            )
        response.raise_for_status()
        return response.json()
