from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from .module import Module


@dataclass
class Flow:
    value: Any
    _source: Optional["Module"] = None
