"""grokbot-kit: delega tarefas a agentes de código headless e acorda a routine do Grok Bot certo."""


def __getattr__(name: str) -> str:
    # `__version__` sob demanda: `importlib.metadata` fica fora do caminho do `emit` (door 6).
    if name == "__version__":
        from importlib.metadata import version

        return version("grokbot-kit")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
