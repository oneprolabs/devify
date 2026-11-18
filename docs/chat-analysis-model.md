# Chat analysis model

Chat event analysis uses the global default model unless `CHAT_ANALYSIS_MODEL_UUID`
is set in the analysis worker's environment. Set it to the UUID of an active LLM
configuration to select that model for note and event extraction, without changing
the global default used by other features. The input budget uses the same model.

The setting selects a model; it does not automatically fail over when a provider
fails. After changing it, recreate the analysis worker using the normal deployment
process and verify a test analysis. Existing failed jobs require a separate retry.
