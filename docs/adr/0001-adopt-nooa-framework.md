# Adopt NOOA (NVIDIA Object-Oriented Agents) as the agent framework

All five existing agents (Schema, SQL, CodeExec, Viz, Coordinator) will be rewritten as NOOA Agent classes. New agents use NOOA from day one.

The current pipeline uses raw Anthropic SDK calls with manual retry loops and ad-hoc prompt construction. NOOA replaces this with typed Python objects — agents are classes, methods are capabilities, type annotations are contracts, and the CodeAct strategy gives the model a Python REPL for iterative problem-solving. This directly solves the big-data context problem: pass-by-reference lets agents operate on millions of rows while only bounded previews enter the LLM context window.

**Considered Options:**
- **Full NOOA migration** (chosen) — rewrite all agents as NOOA classes
- **NOOA for new agents only** — keep existing raw SDK calls, use NOOA for new code
- **NOOA-inspired refactor** — adopt the patterns without the dependency

**Why full migration:** This project serves as both a portfolio showcase and startup MVP. Adopting a cutting-edge NVIDIA framework is a differentiator. The existing codebase has 55 tests providing a safety net, and the NOOA API (v0.0.8) maps cleanly onto the current agent structure. The risk of a v0.0.8 research preview is mitigated by an adapter layer isolating the NOOA dependency.

**Consequences:** 2-week migration window. All agent tests need parallel NOOA equivalents. The Bun sandbox for JS transforms may be replaced by NOOA's Python REPL (separate decision). Must pin `nooa==0.0.8` and track breaking changes.
