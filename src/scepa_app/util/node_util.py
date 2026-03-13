from typing import List, cast
from database_builder_libs.models.node import Node
from database_builder_libs.stores.typedb_v2.typedb_v2_store import RelationData

def format_node(node: Node) -> str:
    lines = []
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
            rel = cast(RelationData, rel)

            lines.append(f"  type: {rel['type']}")

            # roles
            for role, ref in rel.get("roles", {}).items():
                lines.append(
                    f"    {role} -> "
                    f"{ref['entity_type']}({ref['key_attr']}={ref['key']})"
                )

            # attributes
            for attr, value in rel.get("attributes", {}).items():
                lines.append(f"    {attr}: {value}")

    else:
        lines.append("Relations: none")

    return "\n".join(lines)


def print_nodes(nodes: List[Node]):
    for node in nodes:
        print(format_node(node))