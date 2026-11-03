# Lua and native Save

Start with live-results.md for observed behavior. Use the static reports to understand how candidate entry points were found; static traces alone do not prove a working runtime operation.

| File | Read it for |
| --- | --- |
| [live-results.md](live-results.md) | Executed minimized Lua mutation and native Save with fresh-process readback. |
| [native-save.md](native-save.md) | Build-specific Save command and handler analysis; exact-frame ownership and runtime follow-up. |
| [lua-registrations.md](lua-registrations.md) | Registration-table reconstruction, runtime inventory coverage and limits of negative API searches. |
| [runtime-results.metadata.json](runtime-results.metadata.json) | Derived receipts for the initial runtime cases. |
| [lua-registrations.metadata.json](lua-registrations.metadata.json) | Derived registration candidates, address records and positive controls. |

[Return to the research entry point](../../README.md).
