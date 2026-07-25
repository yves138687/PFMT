from pathlib import Path


MARKDOWN_EXTENSIONS = {".md", ".markdown"}
MARKDOWN_MIME_TYPES = {"text/markdown", "text/x-markdown"}
TEXT_EXTENSIONS = {
    ".txt",
    ".log",
    ".csv",
    ".tsv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".ini",
    ".conf",
    ".env",
}


def normalize_extension(filename: str | None) -> str:
    """提取文件扩展名，数据库统一保存小写带点格式。"""

    if not filename:
        return ""
    return Path(filename).suffix.lower()


def detect_file_type(file_ext: str, mime_type: str | None) -> str:
    """根据扩展名和 MIME 粗分业务文件类型。"""

    mime = (mime_type or "").lower()
    if file_ext in MARKDOWN_EXTENSIONS or file_ext in TEXT_EXTENSIONS or mime.startswith("text/"):
        return "text"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if mime == "application/pdf" or file_ext == ".pdf":
        return "pdf"
    return "other"


def is_markdown_file(file_ext: str | None, mime_type: str | None) -> bool:
    """判断文件是否允许走 Markdown 读取接口。"""

    normalized_ext = (file_ext or "").lower()
    normalized_mime = (mime_type or "").lower()
    return normalized_ext in MARKDOWN_EXTENSIONS or normalized_mime in MARKDOWN_MIME_TYPES


def is_text_file(file_ext: str | None, mime_type: str | None, file_type: str | None = None) -> bool:
    """判断文件是否允许按纯文本读取。"""

    normalized_ext = (file_ext or "").lower()
    normalized_mime = (mime_type or "").lower()
    return (
        file_type == "text"
        or normalized_ext in MARKDOWN_EXTENSIONS
        or normalized_ext in TEXT_EXTENSIONS
        or normalized_mime.startswith("text/")
    )
