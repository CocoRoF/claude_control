"""
MCP 요청 라우팅
"""
import logging
from service.mcp_manager.session_manager import SessionManager
from service.mcp_manager.models import MCPRequest, MCPResponse

logger = logging.getLogger(__name__)


class MCPRouter:
    """MCP 요청을 적절한 세션으로 라우팅"""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self._request_id_counter = 0

    def _get_next_request_id(self) -> int:
        """JSON-RPC request ID 생성"""
        self._request_id_counter += 1
        return self._request_id_counter

    async def route_request(self, mcp_request: MCPRequest) -> MCPResponse:
        """
        MCP 요청을 해당 세션의 서버로 라우팅
        """
        session_id = mcp_request.session_id

        # 세션 조회
        process = self.session_manager.get_session(session_id)

        if not process:
            return MCPResponse(
                success=False,
                error=f"Session not found: {session_id}"
            )

        if not process.is_alive():
            return MCPResponse(
                success=False,
                error=f"Session process is not running: {session_id}"
            )

        try:
            # JSON-RPC 2.0 요청 구성
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_request_id(),
                "method": mcp_request.method,
                "params": mcp_request.params or {}
            }

            logger.info(f"Routing request to session {session_id}: {mcp_request.method}")

            # 프로세스로 요청 전송
            response = await process.send_request(jsonrpc_request)

            if response is None:
                return MCPResponse(
                    success=False,
                    error="No response from MCP server (timeout or error)"
                )

            # JSON-RPC 응답 처리
            if "error" in response:
                return MCPResponse(
                    success=False,
                    error=response["error"].get("message", "Unknown error"),
                    data=response.get("error")
                )

            return MCPResponse(
                success=True,
                data=response.get("result")
            )

        except Exception as e:
            logger.error(f"Error routing request: {e}", exc_info=True)
            return MCPResponse(
                success=False,
                error=f"Internal error: {str(e)}"
            )
