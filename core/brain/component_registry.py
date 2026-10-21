from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REGISTRY_PATH = (
    PROJECT_ROOT
    / "core"
    / "brain"
    / "component_registry.yaml"
)


@dataclass
class ComponentRecord:
    """
    One structured ZÆNIA component.

    Static architecture belongs in the registry.

    Dynamic runtime state is derived from the component's
    declared source-of-truth files.
    """

    component_id: str
    name: str
    description: str
    role: str
    scope: str
    local_first: bool

    aliases: list[str]
    provides: list[str]
    depends_on: list[str]
    evidence_paths: list[str]

    state_definition: dict[str, Any]


def load_yaml_file(
    path: Path,
) -> dict[str, Any]:
    """
    Load YAML safely.

    utf-8-sig also tolerates a UTF-8 BOM if Windows software
    happened to add one.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"YAML file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        data = yaml.safe_load(
            file
        ) or {}

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            f"Expected YAML object in: {path}"
        )

    return data


def load_registry() -> dict[str, Any]:
    """
    Load the component-registry document.
    """

    data = load_yaml_file(
        REGISTRY_PATH
    )

    registry = (
        data.get(
            "registry",
            {},
        )
        or {}
    )

    if not isinstance(
        registry,
        dict,
    ):
        raise ValueError(
            "Registry root must be a dictionary."
        )

    components = (
        registry.get(
            "components",
            {},
        )
        or {}
    )

    if not isinstance(
        components,
        dict,
    ):
        raise ValueError(
            "Registry components must be a dictionary."
        )

    return registry


def parse_component(
    component_id: str,
    raw: dict[str, Any],
) -> ComponentRecord:
    """
    Convert raw YAML into a predictable Python structure.
    """

    return ComponentRecord(
        component_id=component_id,
        name=str(
            raw.get(
                "name",
                component_id,
            )
        ),
        description=str(
            raw.get(
                "description",
                "",
            )
        ),
        role=str(
            raw.get(
                "role",
                "unknown",
            )
        ),
        scope=str(
            raw.get(
                "scope",
                "core",
            )
        ),
        local_first=bool(
            raw.get(
                "local_first",
                False,
            )
        ),
        aliases=[
            str(item)
            for item in (
                raw.get(
                    "aliases",
                    [],
                )
                or []
            )
        ],
        provides=[
            str(item)
            for item in (
                raw.get(
                    "provides",
                    [],
                )
                or []
            )
        ],
        depends_on=[
            str(item)
            for item in (
                raw.get(
                    "depends_on",
                    [],
                )
                or []
            )
        ],
        evidence_paths=[
            str(item)
            for item in (
                raw.get(
                    "evidence_paths",
                    [],
                )
                or []
            )
        ],
        state_definition=(
            raw.get(
                "state",
                {},
            )
            or {}
        ),
    )


def get_components() -> dict[str, ComponentRecord]:
    """
    Return all registered ZÆNIA components.
    """

    registry = load_registry()

    raw_components = (
        registry.get(
            "components",
            {},
        )
        or {}
    )

    return {
        component_id: parse_component(
            component_id,
            raw,
        )
        for component_id, raw
        in raw_components.items()
    }


def get_component(
    component_id: str,
) -> ComponentRecord:
    """
    Get one component by its stable registry ID.
    """

    components = (
        get_components()
    )

    if component_id not in components:
        raise KeyError(
            f"Unknown component: {component_id}"
        )

    return components[
        component_id
    ]


def resolve_project_path(
    relative_path: str,
) -> Path:
    """
    Resolve a registry evidence path inside the ZÆNIA project.
    """

    path = Path(
        relative_path
    )

    if path.is_absolute():
        resolved = (
            path.resolve()
        )

    else:
        resolved = (
            PROJECT_ROOT
            / path
        ).resolve()

    project_root_resolved = (
        PROJECT_ROOT.resolve()
    )

    try:
        resolved.relative_to(
            project_root_resolved
        )

    except ValueError as error:
        raise ValueError(
            "Component registry attempted to reference "
            "a path outside the approved ZÆNIA project."
        ) from error

    return resolved


def read_dotted_value(
    data: dict[str, Any],
    dotted_path: str,
) -> Any:
    """
    Read a nested YAML value with dotted notation.

    Example:

        dotted_path:
            voice_output.provider

        YAML:
            voice_output:
              provider: piper

        result:
            piper
    """

    current: Any = data

    for key in dotted_path.split(
        "."
    ):
        if not isinstance(
            current,
            dict,
        ):
            return None

        if key not in current:
            return None

        current = current[
            key
        ]

    return current


def derive_yaml_state(
    state_definition: dict[str, Any],
) -> dict[str, Any]:
    """
    Derive component state directly from its real YAML
    source-of-truth file.

    The component registry does not duplicate those values.
    """

    relative_path = str(
        state_definition.get(
            "path",
            "",
        )
    )

    if not relative_path:
        return {
            "verified": False,
            "reason": (
                "YAML state strategy has no source path."
            ),
            "values": {},
        }

    source_path = (
        resolve_project_path(
            relative_path
        )
    )

    if not source_path.exists():
        return {
            "verified": False,
            "reason": (
                "State source file does not exist."
            ),
            "source": relative_path,
            "values": {},
        }

    data = load_yaml_file(
        source_path
    )

    field_map = (
        state_definition.get(
            "fields",
            {},
        )
        or {}
    )

    values: dict[
        str,
        Any,
    ] = {}

    missing_fields: list[
        str
    ] = []

    for (
        output_name,
        dotted_path,
    ) in field_map.items():

        value = read_dotted_value(
            data,
            str(
                dotted_path
            ),
        )

        values[
            str(
                output_name
            )
        ] = value

        if value is None:
            missing_fields.append(
                str(
                    output_name
                )
            )

    if missing_fields:
        reason = (
            "State source was read, but some "
            "declared fields were not found: "
            + ", ".join(
                missing_fields
            )
        )

    else:
        reason = (
            "State derived from declared "
            "local YAML source."
        )

    return {
        "verified": (
            len(
                missing_fields
            )
            == 0
        ),
        "reason": reason,
        "source": (
            relative_path
        ),
        "values": values,
    }


def derive_evidence_only_state(
    state_definition: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate evidence-only component paths.

    We deliberately do NOT infer runtime state from source-code
    existence alone.
    """

    declared_paths = [
        str(item)
        for item in (
            state_definition.get(
                "paths",
                [],
            )
            or []
        )
    ]

    existing: list[str] = []
    missing: list[str] = []

    for relative_path in declared_paths:
        path = resolve_project_path(
            relative_path
        )

        if path.exists():
            existing.append(
                relative_path
            )

        else:
            missing.append(
                relative_path
            )

    return {
        "verified": False,
        "reason": (
            "Component uses evidence-only state. "
            "File existence does not prove runtime activation."
        ),
        "existing_evidence": (
            existing
        ),
        "missing_evidence": (
            missing
        ),
    }


def derive_component_state(
    component: ComponentRecord,
) -> dict[str, Any]:
    """
    Resolve one component's current known state without asking
    Qwen to guess.

    Supported strategies:

        yaml
        evidence_only
    """

    strategy = str(
        component.state_definition.get(
            "strategy",
            "evidence_only",
        )
    ).lower()

    if strategy == "yaml":
        result = derive_yaml_state(
            component.state_definition
        )

    elif strategy == "evidence_only":
        result = (
            derive_evidence_only_state(
                component.state_definition
            )
        )

    else:
        result = {
            "verified": False,
            "reason": (
                f"Unsupported state strategy: "
                f"{strategy}"
            ),
        }

    return {
        "strategy": strategy,
        **result,
    }


def find_components(
    query: str,
) -> list[ComponentRecord]:
    """
    Search the component registry using:

        component ID
        name
        role
        aliases
        provided capabilities

    This is deterministic architectural lookup, not LLM
    reasoning.
    """

    query = (
        query.strip().lower()
    )

    if not query:
        return []

    results: list[
        tuple[
            int,
            ComponentRecord,
        ]
    ] = []

    for component in (
        get_components().values()
    ):
        score = 0

        component_id = (
            component.component_id.lower()
        )

        name = (
            component.name.lower()
        )

        role = (
            component.role.lower()
        )

        if query == component_id:
            score += 100

        elif query in component_id:
            score += 40

        if query == name:
            score += 80

        elif query in name:
            score += 30

        if query == role:
            score += 70

        elif query in role:
            score += 25

        for alias in component.aliases:
            lowered_alias = (
                alias.lower()
            )

            if query == lowered_alias:
                score += 60

            elif query in lowered_alias:
                score += 20

        for capability in component.provides:
            lowered_capability = (
                capability.lower()
                .replace(
                    "_",
                    " ",
                )
            )

            if query == lowered_capability:
                score += 50

            elif query in lowered_capability:
                score += 15

        if score > 0:
            results.append(
                (
                    score,
                    component,
                )
            )

    results.sort(
        key=lambda item: (
            -item[0],
            item[
                1
            ].component_id,
        )
    )

    return [
        component
        for _, component
        in results
    ]


def format_value(
    value: Any,
) -> str:
    """
    Produce readable command-line values.
    """

    if isinstance(
        value,
        list,
    ):
        return ", ".join(
            str(item)
            for item in value
        )

    if isinstance(
        value,
        bool,
    ):
        return (
            "true"
            if value
            else "false"
        )

    if value is None:
        return "unknown"

    return str(
        value
    )


def print_component(
    component: ComponentRecord,
) -> None:
    """
    Display one architectural component and its derived state.
    """

    state = (
        derive_component_state(
            component
        )
    )

    print()

    print(
        "ZÆNIA Component Registry"
    )

    print()

    print(
        "ID:",
        component.component_id,
    )

    print(
        "Name:",
        component.name,
    )

    print(
        "Role:",
        component.role,
    )

    print(
        "Scope:",
        component.scope,
    )

    print(
        "Local-first:",
        format_value(
            component.local_first
        ),
    )

    print()

    print(
        "Description:",
        component.description,
    )

    print()

    print(
        "Provides:"
    )

    for item in component.provides:
        print(
            f"  - {item}"
        )

    print()

    print(
        "Depends on:"
    )

    for item in component.depends_on:
        print(
            f"  - {item}"
        )

    print()

    print(
        "Evidence paths:"
    )

    for item in component.evidence_paths:
        exists = (
            resolve_project_path(
                item
            ).exists()
        )

        status = (
            "present"
            if exists
            else "missing"
        )

        print(
            f"  - {item} "
            f"[{status}]"
        )

    print()

    print(
        "State strategy:",
        state.get(
            "strategy",
            "",
        ),
    )

    print(
        "State verified:",
        format_value(
            state.get(
                "verified",
                False,
            )
        ),
    )

    print(
        "State reason:",
        state.get(
            "reason",
            "",
        ),
    )

    source = state.get(
        "source"
    )

    if source:
        print(
            "State source:",
            source,
        )

    values = (
        state.get(
            "values",
            {},
        )
        or {}
    )

    if values:
        print()

        print(
            "Derived state:"
        )

        for key, value in (
            values.items()
        ):
            print(
                f"  {key}: "
                f"{format_value(value)}"
            )


def print_registry_list() -> None:
    """
    Show every registered component.
    """

    components = (
        get_components()
    )

    print()

    print(
        "ZÆNIA Component Registry"
    )

    print()

    for component_id in sorted(
        components.keys()
    ):
        component = (
            components[
                component_id
            ]
        )

        print(
            f"{component.component_id}"
            f" — "
            f"{component.name}"
            f" [{component.role}]"
        )


@owner_command('files.read')
def main() -> None:
    """
    Local component-registry command interface.

    Commands:

        list

        show voice_output

        find voice
    """

    parser = argparse.ArgumentParser(
        description=(
            "Inspect ZÆNIA's local component "
            "and capability registry."
        )
    )

    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    subparsers.add_parser(
        "list",
        help=(
            "List registered components."
        ),
    )

    show_parser = (
        subparsers.add_parser(
            "show",
            help=(
                "Show one component and "
                "derive its current state."
            ),
        )
    )

    show_parser.add_argument(
        "component_id",
    )

    find_parser = (
        subparsers.add_parser(
            "find",
            help=(
                "Search component names, roles, "
                "aliases, and capabilities."
            ),
        )
    )

    find_parser.add_argument(
        "query",
        nargs="+",
    )

    args = parser.parse_args()

    if args.command == "list":
        print_registry_list()

        return

    if args.command == "show":
        component = get_component(
            args.component_id
        )

        print_component(
            component
        )

        return

    if args.command == "find":
        query = " ".join(
            args.query
        )

        matches = find_components(
            query
        )

        if not matches:
            print(
                "No matching ZÆNIA "
                "components found."
            )

            return

        print()

        print(
            "ZÆNIA Component Search"
        )

        print(
            "Query:",
            query,
        )

        print()

        for component in matches:
            print(
                f"{component.component_id}"
                f" — "
                f"{component.name}"
                f" [{component.role}]"
            )


if __name__ == "__main__":
    main()