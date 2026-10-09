import json
import logging
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, PermissionDeniedError
from app.core.security import now_utc
from app.models.ai import AiMessage, AiTask
from app.models.user import UserAccount
from app.repositories.ai_repository import AiTaskRepository
from app.schemas.ai import AiTaskCreateRequest, AiTaskListResponse, AiTaskResponse
from app.services.audit_service import AuditService
from app.services.file_service import FileService
from app.services.setting_service import SettingService
from app.utils.ids import new_business_id


AI_CONTEXT_MAX_CHARS = 16000
AI_SELECTED_MAX_CHARS = 12000
AI_TIMEOUT_SECONDS = 60.0
AI_VERIFY_TIMEOUT_SECONDS = 20.0


class AiService:
    """文档页受控 AI 编排服务。"""

    def __init__(self, db: Session, settings):
        self.db = db
        self.settings = settings
        self.repository = AiTaskRepository(db)
        self.setting_service = SettingService(db)
        self.file_service = FileService(db, settings)
        self.audit_service = AuditService(db)
        self.logger = logging.getLogger("pfmt.business")

    def create_task(
        self,
        *,
        payload: AiTaskCreateRequest,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> AiTaskResponse:
        """同步执行一次 AI 任务。"""

        if not self.setting_service.get_bool("ai.feature_enabled", False):
            self.logger.warning(
                "AI 任务创建被拒绝",
                extra={"action": "ai_task_create", "result": "failed", "reason": "feature_disabled"},
            )
            raise PermissionDeniedError("AI 功能未启用")

        provider = self._resolve_provider(payload.provider_id)
        file_info, _parent_path, document_format, content = self.file_service.read_ai_document_context(
            file_id=payload.file_id,
            current_user=current_user,
            client_ip=client_ip,
        )
        context, selected_range, truncated = self._resolve_context(payload, content)
        read_scope = self._build_read_scope(
            file_name=file_info.original_name,
            document_format=document_format,
            is_hidden=file_info.is_hidden,
            selected_range=selected_range,
            truncated=truncated,
        )
        prompt_text = self._build_user_prompt(
            task_type=payload.task_type,
            file_name=file_info.original_name,
            prompt=payload.prompt,
            context=context,
            selected_range=selected_range,
            truncated=truncated,
        )
        task = AiTask(
            task_id=new_business_id("ai_task"),
            task_type=payload.task_type,
            file_id=file_info.file_id,
            selected_range=selected_range,
            read_scope=read_scope,
            model_provider=str(provider.get("id") or provider.get("name") or "openai_compatible"),
            model_name=str(provider.get("model_name") or ""),
            prompt_text=self._prompt_summary(payload.prompt),
            task_status="running",
            created_by=current_user.user_id,
        )
        self.repository.create_task(task)
        self.db.flush()
        self.repository.add_message(
            AiMessage(
                message_id=new_business_id("ai_msg"),
                task_id=task.task_id,
                role="user",
                message_content=self._prompt_summary(prompt_text, max_chars=4000) or "",
            )
        )
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="ai_task_create",
            target_type="file",
            target_id=file_info.file_id,
            result="success",
            detail={
                "task_type": payload.task_type,
                "provider_id": task.model_provider,
                "model_name": task.model_name,
                "read_scope": read_scope,
            },
            client_ip=client_ip,
        )
        self.db.commit()
        self.logger.info(
            "AI 任务已创建",
            extra={
                "action": "ai_task_create",
                "target_type": "file",
                "target_id": file_info.file_id,
                "user_id": current_user.user_id,
                "result": "success",
                "provider_id": task.model_provider,
                "model_name": task.model_name,
                "task_type": payload.task_type,
                "is_hidden": file_info.is_hidden,
                "client_ip": client_ip,
            },
        )

        try:
            answer = self._call_model(provider=provider, prompt_text=prompt_text)
        except Exception as exc:
            self.db.refresh(task)
            task.task_status = "failed"
            task.error_message = str(exc)
            task.completed_at = now_utc()
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="ai_task_complete",
                target_type="ai_task",
                target_id=task.task_id,
                result="failed",
                detail={"task_type": task.task_type, "reason": type(exc).__name__},
                client_ip=client_ip,
            )
            self.db.commit()
            self.logger.warning(
                "AI 任务执行失败",
                extra={
                    "action": "ai_task_complete",
                    "target_type": "ai_task",
                    "target_id": task.task_id,
                    "user_id": current_user.user_id,
                    "result": "failed",
                    "reason": type(exc).__name__,
                    "task_type": task.task_type,
                    "client_ip": client_ip,
                },
            )
            raise

        self.db.refresh(task)
        task.task_status = "success"
        task.completed_at = now_utc()
        self.repository.add_message(
            AiMessage(
                message_id=new_business_id("ai_msg"),
                task_id=task.task_id,
                role="assistant",
                message_content=answer,
            )
        )
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="ai_task_complete",
            target_type="ai_task",
            target_id=task.task_id,
            result="success",
            detail={"task_type": task.task_type, "answer_length": len(answer)},
            client_ip=client_ip,
        )
        self.db.commit()
        self.db.refresh(task)
        self.logger.info(
            "AI 任务执行完成",
            extra={
                "action": "ai_task_complete",
                "target_type": "ai_task",
                "target_id": task.task_id,
                "user_id": current_user.user_id,
                "result": "success",
                "count": len(answer),
                "task_type": task.task_type,
                "client_ip": client_ip,
            },
        )
        return self._to_response(task, answer=answer)

    def list_tasks(
        self,
        *,
        file_id: str,
        limit: int,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> AiTaskListResponse:
        """读取当前文件最近 AI 任务。"""

        self.file_service.read_ai_document_context(
            file_id=file_id,
            current_user=current_user,
            client_ip=client_ip,
        )
        tasks = self.repository.list_by_file_id(file_id=file_id, limit=min(max(limit, 1), 100))
        messages = self.repository.assistant_messages_by_task_ids([task.task_id for task in tasks])
        items = [
            self._to_response(
                task,
                answer=messages.get(task.task_id).message_content if task.task_id in messages else None,
            )
            for task in tasks
        ]
        return AiTaskListResponse(items=items, total=len(items))

    def write_summary(
        self,
        *,
        task_id: str,
        current_user: UserAccount,
        client_ip: str | None,
    ):
        """将成功 summary 任务的 assistant 输出写入文件摘要。"""

        task = self.repository.get_by_task_id(task_id)
        if task is None or task.created_by != current_user.user_id:
            raise AppError("AI 任务不存在", status_code=404, error_code="not_found")
        if task.task_type != "summary" or task.task_status != "success":
            raise AppError("仅成功的总结任务可以写入摘要")

        answer = self.repository.assistant_messages_by_task_ids([task.task_id]).get(task.task_id)
        if answer is None or not answer.message_content.strip():
            raise AppError("AI 总结内容为空")

        file_info, _parent_path, _document_format, _content = self.file_service.read_ai_document_context(
            file_id=task.file_id,
            current_user=current_user,
            client_ip=client_ip,
        )
        response = self.file_service.write_ai_summary(
            file_info=file_info,
            summary_content=answer.message_content.strip(),
            current_user=current_user,
            client_ip=client_ip,
        )
        self.logger.info(
            "AI 总结写入文件摘要",
            extra={
                "action": "ai_write_summary",
                "target_type": "file",
                "target_id": file_info.file_id,
                "user_id": current_user.user_id,
                "result": "success",
                "count": len(answer.message_content.strip()),
                "client_ip": client_ip,
            },
        )
        return response

    def _resolve_provider(self, provider_id: str | None) -> dict[str, Any]:
        provider = self.setting_service.get_active_ai_provider(provider_id)
        if provider is None:
            raise AppError("未配置可用的 AI 模型")
        self._validate_provider_shape(provider)
        return provider

    def _resolve_context(self, payload: AiTaskCreateRequest, document_content: str) -> tuple[str, str | None, bool]:
        selected_text = (payload.selected_text or "").strip()
        if payload.task_type in {"polish", "translate", "continue"}:
            if not selected_text:
                raise AppError("请先选择要处理的文本")
            context = selected_text
            selected_range = "selected_text"
            max_chars = AI_SELECTED_MAX_CHARS
        else:
            context = selected_text or document_content
            selected_range = "selected_text" if selected_text else None
            max_chars = AI_CONTEXT_MAX_CHARS

        truncated = len(context) > max_chars
        if truncated:
            context = context[:max_chars]
        return context, selected_range, truncated

    @staticmethod
    def _build_read_scope(
        *,
        file_name: str,
        document_format: str,
        is_hidden: bool,
        selected_range: str | None,
        truncated: bool,
    ) -> str:
        scope = {
            "current_document": file_name,
            "document_format": document_format,
            "selected_range": selected_range,
            "includes_hidden_content": is_hidden,
            "context_truncated": truncated,
        }
        return json.dumps(scope, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _build_user_prompt(
        *,
        task_type: str,
        file_name: str,
        prompt: str | None,
        context: str,
        selected_range: str | None,
        truncated: bool,
    ) -> str:
        task_instructions = {
            "summary": "请总结当前文档，输出结构清晰、重点明确的中文摘要。",
            "qa": "请只基于给定文档内容回答用户问题；如果文档中没有依据，请明确说明无法从当前文档判断。",
            "polish": "请润色选中文本，保留原意，输出可直接替换的中文结果。",
            "translate": "请将选中文本翻译成中文；如果原文已经是中文，请翻译成自然英文。",
            "continue": "请基于选中文本继续扩写，保持上下文风格一致。",
        }
        user_prompt = (prompt or "").strip()
        parts = [
            f"任务：{task_instructions[task_type]}",
            f"文件：{file_name}",
            f"范围：{'选中文本' if selected_range else '当前文档'}",
        ]
        if truncated:
            parts.append("注意：以下上下文因长度限制已截断，请只基于已提供内容处理。")
        if user_prompt:
            parts.append(f"用户补充要求：{user_prompt}")
        parts.append("上下文：")
        parts.append(context)
        return "\n\n".join(parts)

    def _call_model(self, *, provider: dict[str, Any], prompt_text: str) -> str:
        """调用当前模型供应商；日志只记录元数据，不写入 prompt 或模型回答。"""

        return self._call_openai_compatible(
            provider=provider,
            messages=[
                {
                    "role": "system",
                    "content": "你是 PFMT 文档页的受控 AI 助手。只能基于用户显式提供的上下文回答，不要声称读取了其他文件或知识库。",
                },
                {"role": "user", "content": prompt_text},
            ],
            timeout=AI_TIMEOUT_SECONDS,
            temperature=0.2,
        )

    @classmethod
    def verify_provider(cls, *, provider: dict[str, Any], timeout: float = AI_VERIFY_TIMEOUT_SECONDS) -> str:
        """发送最小模型请求以验证 OpenAI-Compatible 配置。"""

        cls._validate_provider_shape(provider)
        logging.getLogger("pfmt.business").info(
            "AI 供应商连通性验证开始",
            extra={
                "action": "ai_provider_verify",
                "result": "started",
                "provider_id": str(provider.get("id") or provider.get("name") or "openai_compatible"),
                "model_name": str(provider.get("model_name") or ""),
            },
        )
        answer = cls._call_openai_compatible(
            provider=provider,
            messages=[
                {
                    "role": "system",
                    "content": "You are a connectivity checker. Reply with exactly: OK",
                },
                {"role": "user", "content": "OK"},
            ],
            timeout=timeout,
            temperature=0,
        )
        logging.getLogger("pfmt.business").info(
            "AI 供应商连通性验证完成",
            extra={
                "action": "ai_provider_verify",
                "result": "success",
                "provider_id": str(provider.get("id") or provider.get("name") or "openai_compatible"),
                "model_name": str(provider.get("model_name") or ""),
            },
        )
        return answer

    @classmethod
    def _validate_provider_shape(cls, provider: dict[str, Any]) -> None:
        """校验供应商配置完整性；API Key 只参与请求，不进入响应或日志。"""

        if provider.get("provider_type") != "openai_compatible":
            raise AppError("当前仅支持 OpenAI Compatible 类型的 AI 配置")
        if not str(provider.get("base_url") or "").strip():
            raise AppError("AI 模型 API URL 未配置")
        if not str(provider.get("api_key") or "").strip():
            raise AppError("AI 模型 API Key 未配置")
        if not str(provider.get("model_name") or "").strip():
            raise AppError("AI 模型名称未配置")

    @classmethod
    def _call_openai_compatible(
        cls,
        *,
        provider: dict[str, Any],
        messages: list[dict[str, str]],
        timeout: float,
        temperature: float,
    ) -> str:
        endpoint = cls._chat_completions_endpoint(str(provider.get("base_url")))
        model_name = str(provider.get("model_name"))
        api_key = str(provider.get("api_key"))
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        started_at = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                status_code = getattr(response, "status_code", 200)
                logging.getLogger("pfmt.business").info(
                    "AI 模型调用完成",
                    extra={
                        "action": "ai_provider_call",
                        "result": "success",
                        "provider_id": str(provider.get("id") or provider.get("name") or "openai_compatible"),
                        "model_name": model_name,
                        "status_code": status_code,
                        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    },
                )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            detail = cls._provider_error_detail(exc.response)
            logging.getLogger("pfmt.business").warning(
                "AI 模型调用失败",
                extra={
                    "action": "ai_provider_call",
                    "result": "failed",
                    "reason": "http_status_error",
                    "provider_id": str(provider.get("id") or provider.get("name") or "openai_compatible"),
                    "model_name": model_name,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            raise AppError(
                f"AI 模型调用失败：上游返回 {status_code}。{detail}",
                status_code=502,
                error_code="ai_provider_error",
            ) from exc
        except httpx.HTTPError as exc:
            logging.getLogger("pfmt.business").warning(
                "AI 模型连接失败",
                extra={
                    "action": "ai_provider_call",
                    "result": "failed",
                    "reason": exc.__class__.__name__,
                    "provider_id": str(provider.get("id") or provider.get("name") or "openai_compatible"),
                    "model_name": model_name,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            raise AppError(
                f"AI 模型连接失败：{exc.__class__.__name__}",
                status_code=502,
                error_code="ai_provider_error",
            ) from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError("AI 模型响应格式异常", status_code=502, error_code="ai_provider_error") from exc
        if not isinstance(content, str) or not content.strip():
            raise AppError("AI 模型返回空内容", status_code=502, error_code="ai_provider_error")
        return content.strip()

    @staticmethod
    def _chat_completions_endpoint(raw_base_url: str) -> str:
        """兼容用户填写根地址或完整 /chat/completions 地址。"""

        normalized = raw_base_url.strip().rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"

    @staticmethod
    def _provider_error_detail(response: httpx.Response) -> str:
        status_hints = {
            400: "请检查模型名称和请求参数。",
            401: "请检查 API Key 是否正确或是否已启用。",
            403: "请检查 API Key 权限或账户访问权限。",
            404: "请检查 API URL 是否应填写为根地址，例如 https://api.deepseek.com。",
            429: "请求过于频繁或账户额度/限流触发。",
        }
        hint = status_hints.get(response.status_code, "请检查 API URL、模型名称、Key、余额和网络连通性。")
        text = response.text.strip()
        if not text:
            return hint
        compact = " ".join(text.split())
        return f"{hint} 上游响应：{compact[:240]}"

    @staticmethod
    def _prompt_summary(value: str | None, *, max_chars: int = 500) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) <= max_chars:
            return normalized
        return f"{normalized[:max_chars]}..."

    @staticmethod
    def _to_response(task: AiTask, *, answer: str | None) -> AiTaskResponse:
        return AiTaskResponse(
            task_id=task.task_id,
            task_type=task.task_type,
            task_status=task.task_status,
            answer=answer,
            read_scope=task.read_scope,
            model_provider=task.model_provider,
            model_name=task.model_name,
            error_message=task.error_message,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )
