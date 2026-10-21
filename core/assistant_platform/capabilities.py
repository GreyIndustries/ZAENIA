"""Narrow client scopes; sensitive export/restore use local fresh owner proof."""
PLATFORM_CAPABILITIES = frozenset({"assistant.platform.read", "assistant.platform.write",
    "assistant.desktop.manage", "assistant.apps.launch", "assistant.documents.read", "weather.read"})
