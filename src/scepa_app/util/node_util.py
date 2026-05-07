from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from database_builder_libs.models.node import Node


def _format_relation(rel: Mapping[str, object]) -> list[str]:
    lines = [f"  type: {rel['type']}"]

    roles = rel.get("roles", {})
    if isinstance(roles, Mapping):
        for role, ref in roles.items():
            if isinstance(ref, Mapping):
                ref = cast(dict[str, object], ref)
                lines.append(
                    f"    {role} -> {ref['entity_type']}({ref['key_attr']}={ref['key']})"
                )

    attributes = rel.get("attributes", {})
    if isinstance(attributes, Mapping):
        attributes = cast(dict[str, object], attributes)
        for attr, value in attributes.items():
            lines.append(f"    {attr}: {value}")

    return lines


def format_node(node: Node) -> str:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"Entity Type : {node.entity_type}")
    lines.append(f"Node ID     : {node.id}")
    lines.append(f"Key Attr    : {node.key_attribute}")

    lines.append("Payload:")
    for k, v in node.payload_data.items():
        lines.append(f"  {k}: {v}")

    if node.relations:
        lines.append("Relations:")

        for rel in node.relations:
            lines.extend(_format_relation(rel))

    else:
        lines.append("Relations: none")

    return "\n".join(lines)


def print_nodes(nodes: list[Node]) -> None:
    for node in nodes:
        print(format_node(node))
