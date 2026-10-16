"""Runtime-resolved UIA locator descriptions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ControlLocator:
    names: tuple[str, ...] = field(default_factory=tuple)
    control_types: tuple[str, ...] = field(default_factory=tuple)
    automation_ids: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, control: object) -> bool:
        info = control.element_info
        name = (info.name or "").strip().casefold()
        control_type = (info.control_type or "").strip().casefold()
        automation_id = (info.automation_id or "").strip().casefold()
        name_ok = not self.names or name in {value.casefold() for value in self.names}
        type_ok = (not self.control_types or
                   control_type in {value.casefold() for value in self.control_types})
        id_ok = (not self.automation_ids or
                 automation_id in {value.casefold() for value in self.automation_ids})
        return name_ok and type_ok and id_ok
