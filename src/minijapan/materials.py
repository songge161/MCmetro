from __future__ import annotations

import re
from typing import Dict, Iterable, Optional, Set, Tuple

from .models import MaterialSlot

BLOCK_ID_PATTERN = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")


def is_block_id(value: str) -> bool:
    return bool(BLOCK_ID_PATTERN.fullmatch(value))


def resolve_material_slots(
    slots: Iterable[MaterialSlot], available_blocks: Optional[Set[str]] = None
) -> Tuple[Dict[str, str], Dict[str, str], bool]:
    """Resolve semantic materials, optionally against a runtime block registry.

    Without a registry this only selects a deterministic candidate and marks the
    result as unchecked. A future Minecraft bridge can pass the installed block
    IDs to make fallback selection authoritative.
    """
    selected: Dict[str, str] = {}
    sources: Dict[str, str] = {}
    checked = available_blocks is not None
    for slot in slots:
        candidates = list(slot.preferred) + [slot.fallback]
        if available_blocks is None:
            selected[slot.id] = candidates[0]
            sources[slot.id] = "preferred_unchecked"
            continue
        match = next((candidate for candidate in candidates if candidate in available_blocks), None)
        if match is None:
            selected[slot.id] = slot.fallback
            sources[slot.id] = "fallback_missing_from_registry"
        else:
            selected[slot.id] = match
            sources[slot.id] = "preferred" if match in slot.preferred else "fallback"
    return selected, sources, checked


def material_plan(slots: Iterable[MaterialSlot], profile: str) -> Dict[str, object]:
    selected, sources, checked = resolve_material_slots(slots)
    return {
        "profile": profile,
        "availability_checked": checked,
        "selected": selected,
        "resolution_source": sources,
        "notes": "Block availability is unchecked until a Minecraft registry manifest is provided.",
    }
