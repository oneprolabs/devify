from dataclasses import dataclass


@dataclass(frozen=True)
class SourceAdapter:
    channel_type: str
    provider: str
    capabilities: tuple[str, ...]


ADAPTERS = {
    ("wechat", "tauri_upload"): SourceAdapter(
        channel_type="wechat",
        provider="tauri_upload",
        capabilities=("file_import", "attachments"),
    ),
    # These adapters intentionally expose no capability until their local
    # collection and authorization paths are implemented and verified.
    ("whatsapp", "tauri_upload"): SourceAdapter(
        channel_type="whatsapp",
        provider="tauri_upload",
        capabilities=(),
    ),
    ("line", "tauri_upload"): SourceAdapter(
        channel_type="line",
        provider="tauri_upload",
        capabilities=(),
    ),
}


def resolve_adapter(channel_type, provider):
    return ADAPTERS.get((channel_type, provider))


def capabilities_for(channel_type, provider):
    adapter = resolve_adapter(channel_type, provider)
    return list(adapter.capabilities) if adapter else []
