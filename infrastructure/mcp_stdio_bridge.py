import asyncio
import threading
import concurrent.futures
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
import os

class MCPServerBridge:
    def __init__(self, command: str, args: list[str], env: dict[str, str] = None):
        self.command = command
        self.args = args
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        self.env = full_env
        self.tools = []
        
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        self._init_future = concurrent.futures.Future()
        asyncio.run_coroutine_threadsafe(self._init_server(), self.loop)
        self._init_future.result(timeout=25.0) 

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _init_server(self):
        try:
            params = StdioServerParameters(command=self.command, args=self.args, env=self.env)
            self._ctx = stdio_client(params)
            self._read, self._write = await self._ctx.__aenter__()
            self._session = ClientSession(self._read, self._write)
            await self._session.__aenter__()
            await self._session.initialize()
            
            tools_res = await self._session.list_tools()
            self.tools = tools_res.tools
            self._init_future.set_result(True)
        except Exception as e:
            self._init_future.set_exception(e)

    def execute_tool(self, name: str, args: dict) -> dict:
        future = concurrent.futures.Future()
        asyncio.run_coroutine_threadsafe(self._call_tool(name, args, future), self.loop)
        return future.result()

    async def _call_tool(self, name: str, args: dict, future: concurrent.futures.Future):
        try:
            res = await self._session.call_tool(name, arguments=args)
            
            out = ''
            for item in res.content:
                if item.type == 'text':
                    out += item.text + '\n'
                else:
                    out += str(item) + '\n'
            
            future.set_result({'success': not res.isError, 'output': out.strip(), 'error': None if not res.isError else out.strip()})
        except Exception as e:
            future.set_result({'success': False, 'output': '', 'error': str(e)})
