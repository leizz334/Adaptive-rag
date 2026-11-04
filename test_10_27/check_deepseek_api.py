"""检查当前 .env 是否能通过项目的 DeepSeekProvider 完成一次请求。

运行：conda run --no-capture-output -n adaptive-rag python test_10_27/check_deepseek_api.py
仅检查配置（不发请求）：在命令末尾加 --check-only

默认只发一次只读请求，最多生成 128 Token；不重试、不连接业务数据库。
"""

# ruff: noqa: E402 -- 先设置项目导入路径并关闭外部自动追踪。
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for name in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
    os.environ[name] = "false"

import httpx

from app.config.settings import Settings
from app.core.exceptions import LLMProviderError
from app.providers.deepseek import DeepSeekProvider


async def check(*, check_only: bool = False) -> int:
    """返回 0 表示检查通过，1 表示配置或请求失败。"""
    # 使用绝对路径，支持在 IDE 或其他工作目录中运行；系统环境变量仍优先。
    try:
        settings = Settings(_env_file=ROOT / ".env")
    except Exception as exc:
        print(f"FAIL：配置读取失败（{type(exc).__name__}），请检查 .env 的字段格式。")
        return 1

    key = settings.deepseek_api_key.get_secret_value()

    def show(label: str, value: object) -> None:
        # 不输出密钥、请求头或原始错误响应体；上游文本也做密钥脱敏。
        text = str(value)
        if key:
            text = text.replace(key, "[REDACTED]")
        print(f"{label}: {text}")

    show("项目根目录", ROOT)
    show("配置文件", ROOT / ".env")
    show(".env 存在", (ROOT / ".env").is_file())
    show("密钥已识别", settings.llm_configured)
    show("配置模型", settings.deepseek_model)
    if not settings.llm_configured:
        print("FAIL：未读取到 DEEPSEEK_API_KEY，项目此时会选择 OfflineLLMProvider。")
        return 1

    show("项目将选择", "DeepSeekProvider")
    if check_only:
        print("配置读取成功；尚未验证网络、密钥有效性或模型可用性。")
        return 0

    # 只限制本检测的重试次数；不修改 .env 或项目正常运行配置。
    settings = settings.model_copy(update={"llm_max_retries": 1})
    metadata: dict = {}

    async def on_request(request: httpx.Request) -> None:
        # 删除 URL 中可能存在的凭据、查询参数及 fragment。
        safe_url = request.url.copy_with(username=None, password=None, query=None, fragment=None)
        show("实际请求地址", safe_url)

    async def on_response(response: httpx.Response) -> None:
        await response.aread()
        metadata["http_status"] = response.status_code
        show("HTTP 状态", response.status_code)
        show("Content-Type", response.headers.get("content-type", "未返回"))
        if response.status_code == 200:
            try:
                body = response.json()
            except ValueError:
                return
            if isinstance(body, dict):
                metadata["model"] = body.get("model")
                metadata["usage"] = body.get("usage")

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            base_url=settings.deepseek_base_url.rstrip("/"),
            timeout=httpx.Timeout(
                connect=3.0, read=settings.llm_timeout_seconds, write=10.0, pool=5.0
            ),
            event_hooks={"request": [on_request], "response": [on_response]},
        ) as client:
            provider = DeepSeekProvider(settings, client=client)
            response = await provider.generate(
                [{"role": "user", "content": "Reply with exactly: API_OK"}],
                temperature=0.0,
                max_tokens=128,
            )
        if not response.content.strip():
            print("FAIL：接口返回了空回答，尚不能确认项目可正常使用该模型。")
            return 1
        show("接口返回模型", metadata.get("model") or "未返回（不能用配置名代替）")
        usage = metadata.get("usage")
        if isinstance(usage, dict):
            for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = usage.get(field)
                show(field, value if type(value) is int and value >= 0 else "未知")
        else:
            show("Token 使用量", "未知（接口未返回 usage，不能视为 0）")
        show("模型回答", json.dumps(response.content[:500], ensure_ascii=False))
        print("PASS：当前配置可以通过项目 DeepSeekProvider 完成真实 HTTP 调用。")
        print("模型名称由接口提供；第三方网关的底层模型身份无法由本检测独立核实。")
        return 0
    except json.JSONDecodeError:
        print("FAIL：响应不是有效 JSON；HTTP 200 本身不代表模型调用成功。")
        print("请核对网关的 OpenAI 兼容 API 地址，特别是是否需要 /v1 前缀。")
        return 1
    except LLMProviderError as exc:
        show("项目错误码", exc.error_code.value)
        status = metadata.get("http_status")
        if status in {401, 403}:
            print("FAIL：密钥或接口访问权限被拒绝。")
        elif status == 429:
            print("FAIL：接口返回限流或额度限制，请检查网关账户。")
        elif status is not None:
            print("FAIL：上游接口调用失败，请核对 API 路径和模型名称。")
        else:
            print("FAIL：未收到有效 HTTP 响应，请检查网络、代理和超时设置。")
        return 1
    except Exception as exc:
        show("错误类型", type(exc).__name__)
        print("FAIL：请求或响应格式异常，项目 Provider 未能完成调用。")
        return 1
    finally:
        show("总耗时（秒）", f"{time.perf_counter() - started:.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="只检查配置，不调用 API")
    args = parser.parse_args()
    # httpx 默认日志可能包含完整 URL，本脚本只输出上面经过处理的诊断。
    logging.disable(logging.CRITICAL)
    return asyncio.run(check(check_only=args.check_only))


if __name__ == "__main__":
    raise SystemExit(main())
