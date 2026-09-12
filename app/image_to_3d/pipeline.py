from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from collections.abc import Awaitable, Callable
from app.blender.runner import run_blender
from app.image_to_3d.blender_refine import refinement_script
from app.image_to_3d.providers.base import ImageTo3DProvider, Quality, ReconstructionRequest


@dataclass(frozen=True)
class PipelineArtifacts:
    blend: Path
    glb: Path
    previews: list[Path]
    textures: dict[str, Path]
    manifest: Path


class ImageTo3DPipeline:
    def __init__(self, provider: ImageTo3DProvider, progress: Callable[[str], Awaitable[None]] | None = None):
        self.provider = provider
        self.progress = progress

    async def _stage(self, name: str) -> None:
        if self.progress:
            await self.progress(name)

    async def run(self, images: list[Path], prompt: str, quality: Quality, project_dir: Path, rig_required: bool = False) -> PipelineArtifacts:
        if not images or any(not p.is_file() for p in images):
            raise ValueError("At least one existing reference image is required")
        await self._stage("image_analysis")
        analysis = await self.provider.analyze(images, prompt)
        if len(images) == 1 and not analysis.uncertainty:
            analysis = type(analysis)(**{**asdict(analysis), "uncertainty": ["Hidden sides are inferred approximately from one reference"]})
        request = ReconstructionRequest(images, prompt, quality, project_dir, analysis)
        await self._stage("segmentation")
        masks = await self.provider.segment(request)
        await self._stage("depth_estimation")
        depths = await self.provider.estimate_depth(request)
        await self._stage("multiview")
        views = await self.provider.generate_multiview(request)
        await self._stage("mesh_reconstruction")
        mesh = await self.provider.generate_mesh(request, views)
        await self._stage("texture_generation")
        textures = await self.provider.generate_textures(request, mesh)
        from app.image_to_3d.providers.base import ReconstructionResult

        result = ReconstructionResult(mesh, textures, masks, depths, views, {"analysis": asdict(analysis)})
        await self._stage("blender_refinement")
        if result.mesh.suffix.lower() not in {".glb", ".gltf", ".fbx", ".obj", ".blend"}:
            raise RuntimeError("Provider did not return a supported 3D mesh")
        work = project_dir / "blender"
        (work / "previews").mkdir(parents=True, exist_ok=True)
        script = work / "refine.py"
        script.write_text(refinement_script(result.mesh, work, rig_required), encoding="utf-8")
        run_blender(script, project_dir / "logs" / "image_to_3d_blender.log")
        blend = work / "Character.blend"
        glb = work / "Character.glb"
        previews = [work / "previews" / f"{x}.png" for x in ("front", "side", "back", "three_quarter")]
        required = [blend, glb, *previews, work / "quality.json"]
        if any(not p.is_file() or p.stat().st_size == 0 for p in required):
            raise RuntimeError("Blender output set is incomplete; export blocked")
        manifest = project_dir / "image_to_3d.json"
        manifest.write_text(
            json.dumps(
                {
                    "analysis": asdict(analysis),
                    "quality": quality.value,
                    "source_images": [str(x) for x in images],
                    "textures": {k: str(v) for k, v in result.textures.items()},
                    "single_view_inference": len(images) == 1,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return PipelineArtifacts(blend, glb, previews, result.textures, manifest)

    async def revise(self, current_mesh: Path, feedback: str, area: str, revision_dir: Path) -> PipelineArtifacts:
        if not current_mesh.is_file():
            raise FileNotFoundError(current_mesh)
        await self._stage("revision_analysis")
        mesh = await self.provider.revise(current_mesh, feedback, area, revision_dir)
        await self._stage("blender_revision_cleanup")
        work = revision_dir / "blender"
        (work / "previews").mkdir(parents=True, exist_ok=True)
        script = work / "refine.py"
        script.write_text(refinement_script(mesh, work, False), encoding="utf-8")
        run_blender(script, revision_dir / "revision.log")
        blend = work / "Character.blend"
        glb = work / "Character.glb"
        previews = [work / "previews" / f"{x}.png" for x in ("front", "side", "back", "three_quarter")]
        if any(not p.is_file() or p.stat().st_size == 0 for p in [blend, glb, *previews]):
            raise RuntimeError("Revised output failed validation")
        manifest = revision_dir / "revision.json"
        manifest.write_text(json.dumps({"feedback": feedback, "area": area, "source_model": str(current_mesh)}, ensure_ascii=False, indent=2), encoding="utf-8")
        return PipelineArtifacts(blend, glb, previews, {}, manifest)
