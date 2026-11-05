# Grounded answers

The UI sends a student's question to `POST /api/answer`. The server retrieves up to five lecture passages with the existing hybrid retriever, asks an OpenAI-compatible chat-completions endpoint for up to three concise bullets, and only accepts citations that point to those retrieved passages. Citation timestamps are created by the server and rendered as buttons that seek the embedded player.

## Configure a provider

Set these environment variables before starting Uvicorn:

- `LLM_API_KEY`: provider key. Leave empty for a local endpoint.
- `LLM_BASE_URL`: OpenAI-compatible API base URL. Defaults to Groq's endpoint.
- `LLM_MODEL`: model name. Defaults to `llama-3.3-70b-versatile`.

For Groq, set a key and use the defaults for the URL and model. For a local server such as Ollama, point `LLM_BASE_URL` to its OpenAI-compatible `/v1` endpoint and set `LLM_MODEL` to an installed model. `.env.example` has sample values; the application does not load `.env` files automatically, so export the variables in the shell that launches Uvicorn or load them with your preferred environment manager.

If no provider is configured, search and video playback continue to work and the answer panel displays a setup message. If retrieval finds no relevant lecture passages, the LLM is not called.
