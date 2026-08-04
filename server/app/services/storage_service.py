import hashlib
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.models.file import FileInfo
from app.utils.crypto import (
    FRAME_HEADER,
    HEADER,
    KEY_WRAP_VERSION,
    build_header,
    derive_file_key,
    encrypt_chunk,
    generate_storage_name,
    iter_decrypted_chunks,
    load_master_key,
)

STORAGE_DATA_ROOT = "data"
WINDOWS_MAX_COMPONENT_CHARS = 120
WINDOWS_SAFE_MAX_PATH_CHARS = 240


@dataclass(frozen=True)
class StoredObject:
    """文件写入存储层后的结果。"""

    storage_object_name: str
    storage_path: str
    size_bytes: int
    checksum_sha256: str
    key_wrap_version: str | None


@dataclass(frozen=True)
class StoredPath:
    """目录写入存储层后的相对路径信息。"""

    storage_name: str
    storage_path: str


@dataclass(frozen=True)
class ContentRange:
    """明文内容范围，start/end 均为闭区间。"""

    start: int
    end: int
    total: int

    @property
    def length(self) -> int:
        """返回闭区间字节范围的长度。"""

        return self.end - self.start + 1


class StorageService:
    """本地文件存储服务，负责随机对象名、分块写入和分块解密。"""

    def __init__(self, settings: Settings):
        """根据系统配置初始化存储根目录和文件加密主密钥。"""

        self.settings = settings
        self.storage_root = settings.storage_root_path

    def ensure_storage_root_available(self) -> None:
        """启动前确认用户配置的存储根路径存在，避免静默创建空库。"""

        if not self.storage_root.exists() or not self.storage_root.is_dir():
            raise RuntimeError(f"文件存储根路径不存在或不是目录: {self.storage_root}")

    def ensure_data_root(self) -> None:
        """确保存储根路径下的数据树入口存在。"""

        self._validate_absolute_path(self.storage_root / STORAGE_DATA_ROOT)
        (self.storage_root / STORAGE_DATA_ROOT).mkdir(parents=True, exist_ok=True)

    def root_storage_path(self) -> str:
        return STORAGE_DATA_ROOT

    def build_directory_path(self, *, parent_storage_path: str, path_id: str) -> StoredPath:
        """基于父目录真实路径和 path_id 生成固定短度的子目录存储路径。"""

        storage_name = generate_storage_name(self.settings, kind="directory", object_id=path_id)
        relative_path = Path(parent_storage_path) / storage_name
        self._validate_relative_path(relative_path)
        self._validate_absolute_path(self.storage_root / relative_path)
        return StoredPath(storage_name=storage_name, storage_path=relative_path.as_posix())

    def create_directory(self, storage_path: str) -> None:
        """创建真实目录，并校验路径长度位于 Windows 安全范围内。"""

        directory_path = self._absolute_storage_path(storage_path)
        self._validate_absolute_path(directory_path)
        directory_path.mkdir(parents=True, exist_ok=False)

    def move_storage_tree(self, *, source_storage_path: str, target_storage_path: str) -> None:
        """移动真实目录树，目录移动时同步物理层级。"""

        source_path = self._absolute_storage_path(source_storage_path)
        target_path = self._absolute_storage_path(target_storage_path)
        self._validate_absolute_path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.replace(target_path)

    def delete_directory_tree(self, storage_path: str) -> None:
        """删除已经确认在存储根目录内的真实目录树。"""

        directory_path = self._absolute_storage_path(storage_path)
        if directory_path.exists():
            shutil.rmtree(directory_path)

    async def save_upload_file(
        self,
        *,
        upload_file: UploadFile,
        file_id: str,
        encryption_enabled: bool,
        parent_storage_path: str,
    ) -> StoredObject:
        """流式读取 UploadFile 并写入随机对象名文件。"""

        chunk_size = max(64 * 1024, self.settings.upload_chunk_size)
        object_name = generate_storage_name(self.settings, kind="file", object_id=file_id)
        relative_path = Path(parent_storage_path) / object_name
        self._validate_relative_path(relative_path)
        final_path = self.storage_root / relative_path
        self._validate_absolute_path(final_path)
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

    def save_bytes(
        self,
        *,
        content: bytes,
        file_id: str,
        encryption_enabled: bool,
        parent_storage_path: str,
    ) -> StoredObject:
        """将服务内部生成的内容写入新的随机存储对象。"""

        object_name = generate_storage_name(self.settings, kind="file", object_id=file_id)
        relative_path = Path(parent_storage_path) / object_name
        self._validate_relative_path(relative_path)
        final_path = self.storage_root / relative_path
        self._validate_absolute_path(final_path)
        self._write_bytes_to_path(
            content=content,
            file_id=file_id,
            encryption_enabled=encryption_enabled,
            final_path=final_path,
        )
        return StoredObject(
            storage_object_name=object_name,
            storage_path=relative_path.as_posix(),
            size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            key_wrap_version=KEY_WRAP_VERSION if encryption_enabled else None,
        )

    def replace_file_content(self, *, file_info: FileInfo, content: bytes) -> StoredObject:
        """原子替换现有文件对象内容，保留存储对象名和相对路径。"""

        final_path = self._absolute_object_path(file_info.storage_path)
        self._write_bytes_to_path(
            content=content,
            file_id=file_info.file_id,
            encryption_enabled=file_info.encryption_enabled,
            final_path=final_path,
        )
        return StoredObject(
            storage_object_name=file_info.storage_object_name,
            storage_path=file_info.storage_path,
            size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            key_wrap_version=KEY_WRAP_VERSION if file_info.encryption_enabled else None,
        )

    def _write_bytes_to_path(
        self,
        *,
        content: bytes,
        file_id: str,
        encryption_enabled: bool,
        final_path: Path,
    ) -> None:
        chunk_size = max(64 * 1024, self.settings.upload_chunk_size)
        temp_path = final_path.with_suffix(final_path.suffix + ".tmp")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        file_key = derive_file_key(load_master_key(self.settings), file_id) if encryption_enabled else None

        try:
            with temp_path.open("wb") as output:
                if encryption_enabled:
                    output.write(build_header(chunk_size))
                for chunk_index, start in enumerate(range(0, len(content), chunk_size)):
                    chunk = content[start : start + chunk_size]
                    if encryption_enabled and file_key is not None:
                        output.write(encrypt_chunk(file_key, file_id, chunk_index, chunk))
                    else:
                        output.write(chunk)
            temp_path.replace(final_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

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

    def iter_plain_range(self, file_info: FileInfo, content_range: ContentRange) -> Iterator[bytes]:
        """按明文 Range 读取内容，支持加密对象的分块解密和首尾裁剪。"""

        if content_range.start < 0 or content_range.end < content_range.start or content_range.end >= content_range.total:
            raise ValueError("非法内容范围")

        path = self._absolute_object_path(file_info.storage_path)
        if file_info.encryption_enabled:
            yield from self._iter_encrypted_plain_range(file_info, path, content_range)
            return

        chunk_size = max(64 * 1024, self.settings.upload_chunk_size)
        remaining = content_range.length
        with path.open("rb") as file_obj:
            file_obj.seek(content_range.start)
            while remaining > 0:
                chunk = file_obj.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    def _iter_encrypted_plain_range(
        self,
        file_info: FileInfo,
        path: Path,
        content_range: ContentRange,
    ) -> Iterator[bytes]:
        file_key = derive_file_key(load_master_key(self.settings), file_info.file_id)
        with path.open("rb") as file_obj:
            header = file_obj.read(HEADER.size)
            magic, version, chunk_size = HEADER.unpack(header)
            if magic != b"PFMTENC1" or version != 1:
                raise ValueError("不支持的加密文件格式")

            first_chunk_index = content_range.start // chunk_size
            last_chunk_index = content_range.end // chunk_size
            full_frame_size = FRAME_HEADER.size + chunk_size + 16

            for chunk_index in range(first_chunk_index, last_chunk_index + 1):
                plain_start = chunk_index * chunk_size
                plain_end = min(plain_start + chunk_size - 1, file_info.size_bytes - 1)
                plain_len = plain_end - plain_start + 1
                frame_offset = HEADER.size + chunk_index * full_frame_size
                file_obj.seek(frame_offset)
                frame_header = file_obj.read(FRAME_HEADER.size)
                if len(frame_header) != FRAME_HEADER.size:
                    raise ValueError("加密文件分块头不完整")

                stored_chunk_index, nonce, ciphertext_len = FRAME_HEADER.unpack(frame_header)
                if stored_chunk_index != chunk_index:
                    raise ValueError("加密文件分块顺序异常")
                if ciphertext_len != plain_len + 16:
                    raise ValueError("加密文件分块长度异常")

                ciphertext = file_obj.read(ciphertext_len)
                if len(ciphertext) != ciphertext_len:
                    raise ValueError("加密文件分块内容不完整")

                aad = f"{file_info.file_id}:{chunk_index}".encode("utf-8")
                plaintext = AESGCM(file_key).decrypt(nonce, ciphertext, aad)
                slice_start = max(content_range.start - plain_start, 0)
                slice_end = min(content_range.end - plain_start + 1, len(plaintext))
                yield plaintext[slice_start:slice_end]

    def delete_object(self, storage_path: str) -> None:
        """补偿删除已经落盘但元数据入库失败的对象文件。"""

        self._absolute_object_path(storage_path).unlink(missing_ok=True)

    def move_object(self, *, source_storage_path: str, target_parent_storage_path: str, storage_object_name: str) -> str:
        """移动文件对象到新的真实目录，保留短存储文件名。"""

        target_relative_path = Path(target_parent_storage_path) / storage_object_name
        self._validate_relative_path(target_relative_path)
        source_path = self._absolute_object_path(source_storage_path)
        target_path = self.storage_root / target_relative_path
        self._validate_absolute_path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.replace(target_path)
        return target_relative_path.as_posix()

    def _absolute_object_path(self, storage_path: str) -> Path:
        """把数据库里的相对对象路径限制在 storage_root 下。"""

        return self._absolute_storage_path(storage_path)

    def _absolute_storage_path(self, storage_path: str) -> Path:
        """把数据库里的相对存储路径限制在 storage_root 下。"""

        relative_path = Path(storage_path)
        self._validate_relative_path(relative_path)
        return self.storage_root / relative_path

    @staticmethod
    def _validate_relative_path(relative_path: Path) -> None:
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("非法存储对象路径")
        for part in relative_path.parts:
            if len(part) > WINDOWS_MAX_COMPONENT_CHARS:
                raise ConflictError("生成的存储名称超过 Windows 文件名长度限制")

    @staticmethod
    def _validate_absolute_path(path: Path) -> None:
        if len(str(path)) > WINDOWS_SAFE_MAX_PATH_CHARS:
            raise ConflictError("生成的存储路径超过 Windows 安全长度限制")
