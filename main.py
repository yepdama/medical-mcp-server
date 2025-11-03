import uvicorn
import os
from logger.logger_setup import get_logger

logger = get_logger("main")

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    logger.info("Starting MCP server on %s:%s (reload=%s)", host, port, reload)
    uvicorn.run("server.mcp_server:app", host=host, port=port, reload=reload)