# langfuse

Import Langfuse project, prompts, datasets, models, and sessions into Port.

Project-scoped: one Ocean installation uses one Langfuse project API key pair.

Sessions are rebuilt from `v2/observations` (lookback window). Set Langfuse
`session_id` to the Azure Foundry conversation id (`conv_…`) so
`langfuseSession.foundryConversation` links to `azureFoundryConversation`.
