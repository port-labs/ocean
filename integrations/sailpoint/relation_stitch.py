from collections import defaultdict
from typing import DefaultDict, Dict, List, Tuple


class RelationStitcher:
    """
    Optional helper to batch relations after entities exist.
    Use this only if you don't want to include relations in the entity payloads,
    or when you need to guarantee the targets were already created.
    """

    def __init__(self):
        self._links: DefaultDict[Tuple[str, str], List[str]] = defaultdict(list)

    def link(self, source_id: str, relation: str, target_id: str):
        self._links[(source_id, relation)].append(target_id)

    async def flush(self, ocean, blueprint: str):
        """
        Upsert minimal entity payloads with only relations.
        Port will merge relations onto existing entities.
        """
        if not self._links:
            return

        by_source: Dict[str, Dict[str, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for (src, rel), tgts in self._links.items():
            by_source[src][rel].extend(tgts)

        entities = []
        for src, rels in by_source.items():
            entities.append(
                {
                    "identifier": src,
                    "relations": {k: list(set(v)) for k, v in rels.items()},
                }
            )

        await ocean.port_client.ingest_entities(blueprint=blueprint, entities=entities)
        self._links.clear()
