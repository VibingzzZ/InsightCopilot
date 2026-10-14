# 文件上传路由：接收买家 / 客服上传的照片与附件，落盘到 UPLOAD_DIR 并经 /media 静态访问。
#
# 设计取舍（对应接口文档第 2/3 节统一约定）：
# - 成功 / 失败统一走 {data, meta, error} 信封；
# - 仅做扩展名白名单 + 体积上限校验，不做内容扫描（安全脱敏属后续阶段）；
# - 文件名用 uuid 重命名，避免路径穿越与中文 / 空格问题，原文件名仅用于展示；
# - 返回 url（浏览器可访问的 /media/...）与 path（落盘相对路径，供 message.image_path / 视觉识别消费）。

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.core import config
from app.core.envelope import ok
from app.core.errors import ApiError, ErrorCode

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _kind_extensions(kind: str) -> set[str]:
    if kind == "image":
        return config.IMAGE_EXTENSIONS
    if kind == "attachment":
        return config.ATTACHMENT_EXTENSIONS
    return set()


def _safe_suffix(filename: str) -> str:
    """取小写扩展名，无扩展名返回空串。"""
    return Path(filename).suffix.lower()


@router.post("")
async def upload_file(request: Request, file: UploadFile = File(...), kind: str = Form("image")) -> dict:
    """上传一张照片或一份附件，返回可访问的 URL 与落盘路径。

    请求：multipart/form-data，字段 file(必填) + kind(image|attachment, 默认 image)
    成功：{data: {id,url,path,filename,original_name,size,content_type,kind}, meta, error:null}
    """
    if kind not in ("image", "attachment"):
        raise ApiError(400, ErrorCode.INVALID_PARAMETER, "kind 仅支持 image 或 attachment", {"kind": kind})

    original = file.filename or "unnamed"
    suffix = _safe_suffix(original)
    allowed = _kind_extensions(kind)
    if suffix not in allowed:
        raise ApiError(
            415,
            ErrorCode.INVALID_PARAMETER,
            f"不支持的文件类型 {suffix or '(无扩展名)'}，允许：{sorted(allowed)}",
            {"allowed": sorted(allowed)},
        )

    # 边读边校验体积，避免把超大文件整块读进内存
    max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    buf = bytearray()
    while True:
        chunk = await file.read(1024 * 1024)  # 1MB / 次
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise ApiError(
                413,
                ErrorCode.INVALID_PARAMETER,
                f"文件超过大小上限 {config.MAX_UPLOAD_SIZE_MB}MB",
                {"max_mb": config.MAX_UPLOAD_SIZE_MB},
            )
    if not buf:
        raise ApiError(400, ErrorCode.MISSING_REQUIRED_FIELD, "上传文件为空", {})

    stored_name = f"{Path(original).stem[:40]}-{uuid.uuid4().hex[:8]}{suffix}"
    dest = config.UPLOAD_DIR / stored_name
    dest.write_bytes(buf)

    # url 供浏览器 <img>/<a> 直接访问；path 供 message.image_path 与视觉识别消费
    url = f"{config.UPLOAD_URL_PREFIX}/{stored_name}"
    path = f"{config.UPLOAD_DIR.name}/{stored_name}"
    return ok(
        request,
        {
            "id": stored_name,
            "url": url,
            "path": path,
            "filename": stored_name,
            "original_name": original,
            "size": len(buf),
            "content_type": file.content_type or "application/octet-stream",
            "kind": kind,
        },
    )
