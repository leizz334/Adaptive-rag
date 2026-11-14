"""Keyless mode discovery; business endpoints deliberately receive no CORS."""
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.api.dependencies import get_container
from app.api.routes.health import readiness
from app.providers.deepseek import DeepSeekProvider
from app.providers.fake import OfflineLLMProvider
from app.services.container import AppContainer

router=APIRouter(tags=['runtime'])
ORIGINS={f'http://{host}:{port}' for host in ['127.0.0.1','localhost'] for port in [8000,8001]}
MESSAGES={
    'ready':'服务可用。',
    'payment_not_authorized':'本轮尚未授权真实模型消费；请由本地管理员配置服务端授权。',
    'budget_not_ready':'预算状态不可用或存在未确认请求，请先核对账本。',
    'budget_exhausted':'剩余额度不足以预留模型请求，请核对预算。',
    'dependencies_unavailable':'服务依赖尚未就绪，请检查数据库、Redis 和知识库。',
    'unsupported_deployment':'当前服务不是受预算保护的 Real Agent Dev。',
}


class RuntimeStatus(BaseModel):
    mode:Literal['offline','deepseek','unknown']
    available:bool
    reason:str
    message:str
    verification_only:bool=False


@router.get('/runtime-status',response_model=RuntimeStatus)
async def runtime_status(request:Request,response:Response,container:AppContainer=Depends(get_container)) -> RuntimeStatus:
    response.headers['Cache-Control']='no-store'
    origin=request.headers.get('origin')
    if origin in ORIGINS:
        response.headers['Access-Control-Allow-Origin']=origin
        response.headers['Vary']='Origin'
    mode:Literal['offline','deepseek','unknown']='deepseek' if isinstance(container.llm,DeepSeekProvider) else 'offline' if isinstance(container.llm,OfflineLLMProvider) else 'unknown'
    reason='ready'
    if mode=='unknown':
        reason='unsupported_deployment'
    else:
        try:
            ready=await readiness(container)
            if not ready.ready or not all(d.ready for d in ready.dependencies):
                reason='dependencies_unavailable'
        except Exception:
            reason='dependencies_unavailable'
    if mode=='deepseek' and reason=='ready':
        gate=getattr(request.app.state,'real_agent_admission',None)
        if gate is None:
            reason='unsupported_deployment'
        else:
            try:
                status=gate()
                reason='ready' if status.get('available') is True and status.get('reason')=='ready' else status.get('reason')
                if reason not in MESSAGES:
                    reason='budget_not_ready'
            except Exception:
                reason='budget_not_ready'
    message='Offline 服务可用。' if mode=='offline' and reason=='ready' else MESSAGES[reason]
    return RuntimeStatus(mode=mode,available=reason=='ready',reason=reason,message=message,verification_only=bool(getattr(request.app.state,'verification_only',False)))
