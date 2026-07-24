# merge-gate

## Harness providers

The Execution node can use the offline scripted demo, Cursor, Claude Code, or
Gemini CLI. Select the provider and optional model in the Input-node inspector
before creating a run; the selected values are frozen onto that run.

Gemini runs through the installed `gemini` CLI in headless mode inside its
isolated attempt worktree. Authenticate it once with `gemini` and the Google
sign-in flow, set `GEMINI_API_KEY`, or start the backend with your Vertex AI
environment (`GOOGLE_GENAI_USE_VERTEXAI=true` and `GOOGLE_CLOUD_PROJECT`). The
deterministic acceptance engine remains separate from every provider and is
the only component that determines the verdict.
