# openpeon-ext

> extesions / plugins / hooks for [openpeon](https://github.com/PeonPing/openpeon)

---

| openpeon events | When to play |
|---|---|
| `session.start` | Session or workspace opens |
| `task.acknowledge` | Tool accepted work, is processing |
| `task.complete` | Work finished successfully |
| `task.error` | Something failed |
| `input.required` | Blocked, waiting for user |
| `resource.limit` | Rate/token/quota limit hit |

| [Hermes Agent](./.hermes/plugins/openpeon-hook) | openpeon event | Mac | Linux | Windows |
|---|---|---|---|---|
| `on_session_start` | `session.start`    | ✅ | ❌ | ❌ |
| `on_session_end`   | `task.complete`    | ✅ | ❌ | ❌ |
| `pre_tool_call`    | `task.acknowledge` | ✅ | ❌ | ❌ |
| `post_llm_call`    | `task.complete`    | ✅ | ❌ | ❌ |