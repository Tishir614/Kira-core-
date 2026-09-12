from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path


class ObjectStorage(ABC):
    @abstractmethod
    async def put(self, source: Path, key: str) -> str: ...
    @abstractmethod
    async def get(self, key: str, destination: Path) -> Path: ...
    @abstractmethod
    async def delete(self, key: str) -> None: ...
    @abstractmethod
    async def download_url(self, key: str, expires: int = 3600) -> str: ...
class S3ObjectStorage(ObjectStorage):
    def __init__(self, bucket: str, endpoint_url: str, access_key: str, secret_key: str, region: str = "us-east-1"):
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=endpoint_url, aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)

    @staticmethod
    def validate_key(key: str) -> str:
        path = Path(key)
        if path.is_absolute() or ".." in path.parts or not key.startswith("users/"):
            raise ValueError("unsafe object key")
        return key

    async def put(self, source: Path, key: str) -> str:
        key = self.validate_key(key)
        await asyncio.to_thread(self.client.upload_file, str(source), self.bucket, key)
        return key

    async def get(self, key: str, destination: Path) -> Path:
        key = self.validate_key(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self.client.download_file, self.bucket, key, str(destination))
        return destination

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=self.validate_key(key))

    async def download_url(self, key: str, expires: int = 3600) -> str:
        return await asyncio.to_thread(
            self.client.generate_presigned_url, "get_object", Params={"Bucket": self.bucket, "Key": self.validate_key(key)}, ExpiresIn=min(expires, 86400)
        )
