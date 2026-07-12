from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ClientNaming:
    base: str
    dashed: str
    underscored: str
    camel: str


class NamingPolicy(Protocol):
    def __call__(self, project: str) -> ClientNaming: ...


@dataclass(frozen=True)
class DefaultNamingPolicy:
    root_name: str

    def __call__(self, project: str) -> ClientNaming:
        base = f"{project.rsplit('/', maxsplit=1)[-1]}-client"
        dashed = f"{self.root_name}-{base}"
        underscored = dashed.replace("-", "_")
        camel = f"{self.root_name.capitalize()}{''.join(part.capitalize() for part in base.split('-'))}"
        return ClientNaming(base=base, dashed=dashed, underscored=underscored, camel=camel)
