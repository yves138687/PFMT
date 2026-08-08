import base64
import hashlib
import os
import secrets
import struct
from collections.abc import Iterator
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


MAGIC = b"PFMTENC1"
HEADER = struct.Struct(">8sBI")
FRAME_HEADER = struct.Struct(">Q12sI")
KEY_WRAP_VERSION = "aesgcm-chunked-v1"
STORAGE_NAME_VERSION = "v1"


def normalize_key_material(raw_value: str) -> bytes:
    """将配置里的密钥材料规范化为 32 字节密钥。"""

    normalized = raw_value.strip()
    if not normalized:
        raise RuntimeError("文件加密密钥未配置")
    padded = normalized + "=" * (-len(normalized) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
        if len(decoded) == 32:
            return decoded
    except ValueError:
        pass
    return hashlib.sha256(normalized.encode("utf-8")).digest()


def derive_file_key(master_key: bytes, file_id: str) -> bytes:
    """基于主密钥和 file_id 派生每个文件独立使用的 AES-256-GCM 密钥。"""

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=file_id.encode("utf-8"),
        info=b"pfmt-file-content-v1",
    )
    return hkdf.derive(master_key)


def generate_storage_name(_settings, *, kind: str, object_id: str) -> str:
    """生成固定短度的本地存储名，避免明文名或长密文撑爆 Windows 路径。"""

    if kind not in {"directory", "file"}:
        raise ValueError("不支持的存储名称类型")

    prefix = "d1" if kind == "directory" else "f1"
    digest = hashlib.sha256(f"{STORAGE_NAME_VERSION}:{kind}:{object_id}".encode("utf-8")).digest()
    random_bytes = secrets.token_bytes(8)
    token = base64.urlsafe_b64encode(digest[:8] + random_bytes).decode("ascii").rstrip("=")
    suffix = ".pfmt" if kind == "file" else ""
    return f"{prefix}_{token}{suffix}"


def build_header(chunk_size: int) -> bytes:
    """生成 chunked AES-GCM 文件头，记录版本与分块大小。"""

    return HEADER.pack(MAGIC, 1, chunk_size)


def encrypt_chunk(file_key: bytes, file_id: str, chunk_index: int, plaintext: bytes) -> bytes:
    """加密单个分块；每块独立 nonce 和认证标签，便于流式解密。"""

    nonce = os.urandom(12)
    aad = f"{file_id}:{chunk_index}".encode("utf-8")
    ciphertext = AESGCM(file_key).encrypt(nonce, plaintext, aad)
    return FRAME_HEADER.pack(chunk_index, nonce, len(ciphertext)) + ciphertext


def iter_decrypted_chunks(path: Path, file_key: bytes, file_id: str) -> Iterator[bytes]:
    """按分块读取并解密本地密文对象，任何分块篡改都会触发解密失败。"""

    with path.open("rb") as file_obj:
        header = file_obj.read(HEADER.size)
        magic, version, _chunk_size = HEADER.unpack(header)
        if magic != MAGIC or version != 1:
            raise ValueError("不支持的加密文件格式")

        expected_index = 0
        while True:
            frame_header = file_obj.read(FRAME_HEADER.size)
            if not frame_header:
                break
            if len(frame_header) != FRAME_HEADER.size:
                raise ValueError("加密文件分块头不完整")

            chunk_index, nonce, ciphertext_len = FRAME_HEADER.unpack(frame_header)
            if chunk_index != expected_index:
                raise ValueError("加密文件分块顺序异常")

            ciphertext = file_obj.read(ciphertext_len)
            if len(ciphertext) != ciphertext_len:
                raise ValueError("加密文件分块内容不完整")

            aad = f"{file_id}:{chunk_index}".encode("utf-8")
            yield AESGCM(file_key).decrypt(nonce, ciphertext, aad)
            expected_index += 1
