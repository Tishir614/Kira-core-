from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from app.image_to_3d.providers.base import Analysis, ImageTo3DProvider, ReconstructionRequest, ReconstructionResult


class HTTPImageTo3DProvider(ImageTo3DProvider):
    """Adapter for a reconstruction service implementing Kira's documented REST contract."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 1800):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Provider URL must be HTTP(S)")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def _post(self, endpoint: str, payload: dict[str, Any], images: list[Path] | None = None) -> dict[str, Any]:
        import httpx

        files = []
        handles = []
        try:
            for image in images or []:
                handle = image.open("rb")
                handles.append(handle)
                files.append(("images", (image.name, handle, "application/octet-stream")))
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.post(f"{self.base_url}{endpoint}", headers=self._headers(), data={"request": json.dumps(payload)}, files=files)
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError("Provider returned invalid JSON")
            return data
        finally:
            for handle in handles:
                handle.close()

    async def _download(self, url: str, destination: Path) -> Path:
        import httpx

        if not url.startswith(self.base_url + "/"):
            raise RuntimeError("Provider artifact URL is outside configured origin")
        destination.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            async with client.stream("GET", url, headers=self._headers()) as response:
                response.raise_for_status()
                with destination.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        output.write(chunk)
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("Provider returned an empty artifact")
        return destination

    async def analyze(self, images: list[Path], prompt: str) -> Analysis:
        data = await self._post("/v1/analyze", {"prompt": prompt}, images)
        return Analysis(**data)

    async def segment(self, request: ReconstructionRequest) -> dict[str, Path]:
        data = await self._post("/v1/segment", self._payload(request), request.images)
        result = {}
        allowed = {
            "background",
            "body",
            "head",
            "hair_fur",
            "ears",
            "eyes",
            "mouth",
            "nose",
            "arms",
            "hands_paws",
            "legs",
            "feet",
            "tail",
            "clothes",
            "accessories",
        }
        for label, url in data.get("masks", {}).items():
            if label in allowed:
                result[label] = await self._download(url, request.project_dir / "segmentation" / f"{label}.png")
        if not result:
            raise RuntimeError("Provider returned no semantic masks")
        return result

    async def estimate_depth(self, request: ReconstructionRequest) -> list[Path]:
        data = await self._post("/v1/depth", self._payload(request), request.images)
        result = []
        for index, url in enumerate(data.get("depth_maps", [])):
            result.append(await self._download(url, request.project_dir / "depth" / f"{index:02d}.png"))
        if not result:
            raise RuntimeError("Provider returned no depth maps")
        return result

    async def generate_multiview(self, request: ReconstructionRequest) -> dict[str, Path]:
        data = await self._post("/v1/multiview", self._payload(request), request.images)
        result = {}
        for view, url in data.get("views", {}).items():
            result[view] = await self._download(url, request.project_dir / "multiview" / f"{view}.png")
        return result

    async def generate_mesh(self, request: ReconstructionRequest, views: dict[str, Path]) -> Path:
        data = await self._post("/v1/mesh", {**self._payload(request), "view_names": list(views)}, request.images + list(views.values()))
        return await self._download(data["mesh_url"], request.project_dir / "reconstruction" / "source.glb")

    async def generate_textures(self, request: ReconstructionRequest, mesh: Path) -> dict[str, Path]:
        data = await self._post("/v1/textures", self._payload(request), request.images + [mesh])
        result = {}
        for channel, url in data.get("textures", {}).items():
            result[channel] = await self._download(url, request.project_dir / "textures" / f"{channel}.png")
        return result

    async def revise(self, current_mesh: Path, feedback: str, area: str, project_dir: Path) -> Path:
        data = await self._post("/v1/revise", {"feedback": feedback, "area": area, "preserve_identity": True, "modify_existing_mesh": True}, [current_mesh])
        return await self._download(data["mesh_url"], project_dir / "revised_source.glb")

    async def reconstruct(self, request: ReconstructionRequest) -> ReconstructionResult:
        analysis = request.analysis or await self.analyze(request.images, request.prompt)
        enriched = ReconstructionRequest(request.images, request.prompt, request.quality, request.project_dir, analysis)
        masks = await self.segment(enriched)
        depth = await self.estimate_depth(enriched)
        views = await self.generate_multiview(enriched)
        mesh = await self.generate_mesh(enriched, views)
        textures = await self.generate_textures(enriched, mesh)
        return ReconstructionResult(mesh, textures, masks, depth, views, {"analysis": analysis.__dict__, "single_view_inference": len(request.images) == 1})

    @staticmethod
    def _payload(request: ReconstructionRequest) -> dict[str, Any]:
        return {
            "prompt": request.prompt,
            "quality": request.quality.value,
            "analysis": request.analysis.__dict__ if request.analysis else None,
            "require_volumetric_mesh": True,
            "preserve_identity": True,
        }
