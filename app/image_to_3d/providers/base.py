from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Quality(StrEnum):
    DRAFT = "draft"
    GOOD = "good"
    HIGH = "high"


@dataclass(frozen=True)
class Analysis:
    subject_type: str
    traits: list[str]
    proportions: dict[str, float | str]
    palette: list[str]
    materials: list[str]
    view_labels: list[str]
    uncertainty: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReconstructionRequest:
    images: list[Path]
    prompt: str
    quality: Quality
    project_dir: Path
    analysis: Analysis | None = None


@dataclass(frozen=True)
class ReconstructionResult:
    mesh: Path
    textures: dict[str, Path]
    masks: dict[str, Path]
    depth_maps: list[Path]
    generated_views: dict[str, Path]
    metadata: dict[str, Any]


class ImageTo3DProvider(ABC):
    """Provider contract. Implementations must return volumetric geometry, never cards."""

    @abstractmethod
    async def analyze(self, images: list[Path], prompt: str) -> Analysis: ...
    @abstractmethod
    async def segment(self, request: ReconstructionRequest) -> dict[str, Path]: ...
    @abstractmethod
    async def estimate_depth(self, request: ReconstructionRequest) -> list[Path]: ...
    @abstractmethod
    async def generate_multiview(self, request: ReconstructionRequest) -> dict[str, Path]: ...
    @abstractmethod
    async def generate_mesh(self, request: ReconstructionRequest, views: dict[str, Path]) -> Path: ...
    @abstractmethod
    async def generate_textures(self, request: ReconstructionRequest, mesh: Path) -> dict[str, Path]: ...
    @abstractmethod
    async def revise(self, current_mesh: Path, feedback: str, area: str, project_dir: Path) -> Path: ...
    @abstractmethod
    async def reconstruct(self, request: ReconstructionRequest) -> ReconstructionResult: ...
