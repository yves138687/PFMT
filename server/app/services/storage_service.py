import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.models.file import FileInfo
from app.utils.crypto import (
    KEY_WRAP_VERSION,
    build_header,
    derive_file_key,
    encrypt_chunk,
    iter_decrypted_chunks,
    load_master_key,
)


@dataclass(frozen=True)
class StoredObject:
    """文件写入存储层后的结果。"""

    storage_object_name: str
    storage_path: str
    size_bytes: int
    checksum_sha256: str
    key_wrap_version: str | None


class StorageService:
    """本地文件存储服务，负责随机对象名、分块写入和分块解密。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage_root = settings.storage_root_path

    async def save_upload_file(
        self,
        *,
        upload_file: UploadFile,
        file_id: str,
        encryption_enabled: bool,
    ) -> StoredObject:
        """流式读取 UploadFile 并写入随机对象名文件。"""

        chunk_size = max(64 * 1024, self.settings.upload_chunk_size)
        object_name = f"{uuid4().hex}.pfmt"
        shard = object_name[:2]
        relative_path = Path("objects") / shard / object_name
        final_path = self.storage_root / relative_path
        temp_path = final_path.with_suffix(final_path.suffix + ".tmp")
        final_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        size_bytes = 0
        chunk_index = 0
        file_key = None
        if encryption_enabled:
            file_key = derive_file_key(load_master_key(self.settings), file_id)

        try:
            with temp_path.open("wb") as output:
                if encryption_enabled:
                    output.write(build_header(chunk_size))

                while True:
                    chunk = await upload_file.read(chunk_size)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    hasher.update(chunk)
                    if encryption_enabled and file_key is not None:
                        output.write(encrypt_chunk(file_key, file_id, chunk_index, chunk))
                        chunk_index += 1
                    else:
                        output.write(chunk)

            temp_path.replace(final_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            raise

        return StoredObject(
            storage_object_name=object_name,
            storage_path=relative_path.as_posix(),
            size_bytes=size_bytes,
            checksum_sha256=hasher.hexdigest(),
            key_wrap_version=KEY_WRAP_VERSION if encryption_enabled else None,
        )

    def iter_content_chunks(self, file_info: FileInfo) -> Iterator[bytes]:
        """根据文件元数据流式读取明文内容。"""

        path = self._absolute_object_path(file_info.storage_path)
        if file_info.encryption_enabled:
            file_key = derive_file_key(load_master_key(self.settings), file_info.file_id)
            yield from iter_decrypted_chunks(path, file_key, file_info.file_id)
            return

        chunk_size = max(64 * 1024, self.settings.upload_chunk_size)
        with path.open("rb") as file_obj:
            while True:
                chunk = file_obj.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def delete_object(self, storage_path: str) -> None:
        """补偿删除已经落盘但元数据入库失败的对象文件。"""

        self._absolute_object_path(storage_path).unlink(missing_ok=True)

    def _absolute_object_path(self, storage_path: str) -> Path:
        """把数据库里的相对对象路径限制在 storage_root 下。"""

        relative_path = Path(storage_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("非法存储对象路径")
        return self.storage_root / relative_path
