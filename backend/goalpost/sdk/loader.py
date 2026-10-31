"""Discover connectors: one folder per connector under `connectors/`, each with `connector.py`."""

import importlib.util
import inspect
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from goalpost.sdk import SDK_VERSION, Connector

log = logging.getLogger(__name__)

type ConnectorClass = type[Connector[Any]]


class ConnectorLoadError(Exception):
    pass


@dataclass
class Registry:
    """Installed connector types by manifest id, plus folders that failed to load."""

    types: dict[str, ConnectorClass] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def get(self, type_id: str) -> ConnectorClass | None:
        return self.types.get(type_id)


def load_connector(folder: Path) -> ConnectorClass:
    """Import `folder/connector.py` and return its single Connector subclass."""
    path = folder / "connector.py"
    if not path.is_file():
        raise ConnectorLoadError(f"{folder.name}: no connector.py")

    module_name = f"goalpost_connectors.{folder.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ConnectorLoadError(f"{folder.name}: connector.py can't be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # pydantic resolves annotations through sys.modules
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise ConnectorLoadError(f"{folder.name}: import failed: {exc}") from exc

    classes = [
        obj
        for obj in vars(module).values()
        if inspect.isclass(obj)
        and issubclass(obj, Connector)
        and obj.__module__ == module_name
        and not inspect.isabstract(obj)
    ]
    if len(classes) != 1:
        raise ConnectorLoadError(
            f"{folder.name}: expected one Connector subclass, found {len(classes)}"
        )
    cls = classes[0]
    manifest = getattr(cls, "manifest", None)
    if manifest is None:
        raise ConnectorLoadError(f"{folder.name}: {cls.__name__} has no manifest")
    if manifest.sdk_version != SDK_VERSION:
        raise ConnectorLoadError(
            f"{folder.name}: built for SDK {manifest.sdk_version}, this core runs SDK {SDK_VERSION}"
        )
    if manifest.id != folder.name:
        raise ConnectorLoadError(
            f"{folder.name}: manifest id {manifest.id!r} must match the folder"
        )
    return cls


def discover(root: Path) -> Registry:
    """Load every connector folder under `root`.

    Folders starting with _ or . (like _template) and folders without a connector.py yet
    (placeholders for planned connectors) are skipped silently.
    """
    registry = Registry()
    if not root.is_dir():
        log.warning("Connectors folder %s not found", root)
        return registry
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if folder.name.startswith(("_", ".")) or not (folder / "connector.py").is_file():
            continue
        try:
            cls = load_connector(folder)
        except ConnectorLoadError as exc:
            log.warning("Skipping connector: %s", exc)
            registry.errors[folder.name] = str(exc)
            continue
        registry.types[cls.manifest.id] = cls
    return registry
