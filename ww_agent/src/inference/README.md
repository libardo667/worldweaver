# Inference client

`InferenceClient` is the small OpenAI-compatible language-model boundary used by the predictive pulse,
doula, and other explicit cognition sites. It provides plain-text and structured JSON completion
methods, centralizes provider authentication/timeouts, and keeps transport details out of runtime
modules.

Callers own their prompt contract, token budget, and fallback behavior. Treat model output as an
untrusted proposal: validate structured responses and preserve a deterministic no-action path when a
completion fails. Do not create model-specific SDK dependencies in cognitive modules.

The default endpoint/model come from `WW_INFERENCE_URL` and `WW_INFERENCE_MODEL`; the API key comes from
`WW_INFERENCE_KEY`.
