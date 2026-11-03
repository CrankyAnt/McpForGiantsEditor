-- Name: MCP Probe Dispatch
-- Description: Process one request in the isolated native-message experiment
-- Namespace: global
-- Hide: no
-- AlwaysLoaded: no
assert(type(MCP_NATIVE_DISPATCH)=="function","mcp_dispatch_not_initialized")
MCP_NATIVE_DISPATCH()