import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controller.claude_controller import router as claude_router, session_manager
from service.redis.redis_client import RedisClient, get_redis_client
from service.pod.pod_info import init_pod_info, get_pod_info
from service.middleware.session_router import SessionRoutingMiddleware
from service.proxy.internal_proxy import get_internal_proxy
from service.mcp_loader import MCPLoader, get_global_mcp_config
import uvicorn

# .env 파일 로드
try:
    from dotenv import load_dotenv
    # 프로젝트 루트의 .env 파일 로드
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment from {env_path}")
    else:
        # .env.example이 있으면 안내 메시지 출력
        example_path = Path(__file__).parent / ".env.example"
        if example_path.exists():
            print(f"ℹ️  No .env file found. Copy .env.example to .env and configure it.")
except ImportError:
    print("⚠️  python-dotenv not installed. Environment variables must be set manually.")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_claude_control_logo():
    """Claude Control 로고 출력"""
    logo = """
     ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗     ██████╗ ██████╗ ███╗   ██╗████████╗██████╗  ██████╗ ██╗     
    ██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝    ██╔════╝██╔═══██╗████╗  ██║╚══██╔══╝██╔══██╗██╔═══██╗██║     
    ██║     ██║     ███████║██║   ██║██║  ██║█████╗      ██║     ██║   ██║██╔██╗ ██║   ██║   ██████╔╝██║   ██║██║     
    ██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝      ██║     ██║   ██║██║╚██╗██║   ██║   ██╔══██╗██║   ██║██║     
    ╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗    ╚██████╗╚██████╔╝██║ ╚████║   ██║   ██║  ██║╚██████╔╝███████╗
     ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝

    🤖 Claude Code Multi-Session Management System 🤖
    """
    logger.info(logo)


def print_step_banner(step: str, title: str, description: str = ""):
    """단계별 배너 출력"""
    banner = f"""
    ┌{'─' * 60}┐
    │  {step}: {title:<52}│
    {f'│  {description:<58}│' if description else ''}
    └{'─' * 60}┘
    """
    logger.info(banner)


def init_redis_client(app: FastAPI) -> RedisClient:
    """Redis 클라이언트 초기화 및 app.state에 등록"""
    redis_client = RedisClient()
    
    # FastAPI app.state에 등록하여 전역 접근 가능하게 함
    app.state.redis_client = redis_client
    
    if redis_client.is_connected:
        logger.info("✅ Redis 클라이언트 초기화 완료")
        stats = redis_client.get_stats()
        logger.info(f"   - Host: {stats['host']}:{stats['port']}")
        logger.info(f"   - DB: {stats['db']}")
        if stats.get('redis_info'):
            logger.info(f"   - Redis Version: {stats['redis_info'].get('version')}")
    else:
        logger.warning("⚠️  Redis 연결 실패 - 로컬 메모리 모드로 동작")
    
    return redis_client


def get_app_redis_client(app: FastAPI) -> RedisClient:
    """app.state에서 Redis 클라이언트 가져오기"""
    return getattr(app.state, 'redis_client', None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    print_claude_control_logo()
    print_step_banner("START", "CLAUDE CONTROL STARTUP", "Initializing Claude session management system")
    logger.info("Starting Claude Control")
    
    # Pod 정보 초기화
    print_step_banner("POD", "POD INFO", "Initializing pod information...")
    pod_info = init_pod_info()
    app.state.pod_info = pod_info
    logger.info(f"   - Pod Name: {pod_info.pod_name}")
    logger.info(f"   - Pod IP: {pod_info.pod_ip}")
    logger.info(f"   - Service Port: {pod_info.service_port}")
    
    # Redis 클라이언트 초기화 및 app.state에 등록
    print_step_banner("REDIS", "REDIS CONNECTION", "Connecting to Redis server...")
    redis_client = init_redis_client(app)
    
    # SessionManager에 Redis 클라이언트 주입
    session_manager.set_redis_client(redis_client)
    
    # MCP 설정 및 도구 자동 로드
    print_step_banner("MCP", "MCP LOADER", "Loading MCP configs and tools...")
    mcp_loader = MCPLoader()
    mcp_config = mcp_loader.load_all()
    app.state.mcp_loader = mcp_loader
    app.state.global_mcp_config = mcp_config
    
    # SessionManager에 글로벌 MCP 설정 주입
    session_manager.set_global_mcp_config(mcp_config)
    logger.info(f"   - MCP Servers: {mcp_loader.get_server_count()}")
    logger.info(f"   - Custom Tools: {mcp_loader.get_tool_count()}")
    
    print_step_banner("READY", "CLAUDE CONTROL READY", "All systems operational! 🎉")
    logger.info("🎉 Claude Control startup complete! Ready to serve requests.")
    
    yield
    
    print_step_banner("SHUTDOWN", "CLAUDE CONTROL SHUTDOWN", "Cleaning up sessions...")
    logger.info("Shutting down Claude Control")
    
    # Internal Proxy 클라이언트 종료
    proxy = get_internal_proxy()
    await proxy.close()
    
    # Internal Proxy 클라이언트 종료
    proxy = get_internal_proxy()
    await proxy.close()

    # 모든 세션 정리 (전체 타임아웃 10초)
    async def cleanup_all_sessions():
        sessions = session_manager.list_sessions()
        # 병렬로 세션 정리
        cleanup_tasks = [
            session_manager.delete_session(session.session_id)
            for session in sessions
        ]
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    try:
        await asyncio.wait_for(cleanup_all_sessions(), timeout=10.0)
        logger.info("All sessions cleaned up successfully")
    except asyncio.TimeoutError:
        logger.warning("Session cleanup timed out, some processes may still be running")


# FastAPI 앱 생성
app = FastAPI(
    title="Claude Control",
    description="Claude Code 멀티 세션 관리 시스템",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정 (백엔드에서 접근 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 오리진으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 세션 라우팅 미들웨어 (Multi-pod 환경에서 세션 기반 프록시)
# 주의: add_middleware는 역순으로 실행됨 (마지막에 추가한 것이 먼저 실행)
app.add_middleware(SessionRoutingMiddleware)


@app.get("/")
async def root():
    """헬스체크"""
    pod_info = get_pod_info()
    return {
        "service": "Claude Control",
        "status": "running",
        "pod_name": pod_info.pod_name,
        "pod_ip": pod_info.pod_ip,
        "sessions_count": len(session_manager.sessions)
    }


@app.get("/health")
async def health_check():
    """상세 헬스체크"""
    sessions = session_manager.list_sessions()
    pod_info = get_pod_info()
    
    # Redis 상태 확인 (app.state에서 가져오기)
    redis_client = get_app_redis_client(app)
    redis_status = "disconnected"
    if redis_client and redis_client.is_connected:
        redis_status = "connected" if redis_client.health_check() else "error"
    
    # 현재 Pod에서 실행 중인 세션 수
    local_sessions = len(session_manager.sessions)

    return {
        "status": "healthy",
        "pod_name": pod_info.pod_name,
        "pod_ip": pod_info.pod_ip,
        "redis": redis_status,
        "total_sessions": len(sessions),
        "local_sessions": local_sessions,
        "running_sessions": sum(1 for s in sessions if s.status == "running"),
        "error_sessions": sum(1 for s in sessions if s.status == "error")
    }


@app.get("/redis/stats")
async def redis_stats():
    """Redis 상태 및 통계"""
    redis_client = get_app_redis_client(app)
    if redis_client:
        return redis_client.get_stats()
    return {"error": "Redis client not initialized"}


# Claude 라우터 등록
app.include_router(claude_router)

if __name__ == "__main__":
    try:
        host = os.environ.get("APP_HOST", "0.0.0.0")
        port = int(os.environ.get("APP_PORT", "8000"))
        debug = os.environ.get("DEBUG_MODE", "false").lower() in ('true', '1', 'yes', 'on')

        print(f"Starting server on {host}:{port} (debug={debug})")

        if debug:
            # reload 모드에서는 import string 형식으로 전달
            uvicorn.run("main:app", host=host, port=port, reload=True)
        else:
            # 일반 모드에서는 app 객체 직접 전달
            uvicorn.run(app, host=host, port=port, reload=False)
    except Exception as e:
        logger.warning(f"Failed to load config for uvicorn: {e}")
        logger.info("Using default values for uvicorn")
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)