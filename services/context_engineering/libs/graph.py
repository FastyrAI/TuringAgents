from __future__ import annotations

from typing import Iterable, List, Optional, Tuple
import json
import time

from neo4j import GraphDatabase  # type: ignore

from .models import Message, Entity, Fact, Summary
from .config import EPHEMERAL_TTL_SECONDS
from .metrics import GRAPH_NODES_GAUGE


class GraphClient:
    """Thin wrapper around Neo4j for context engineering v2.

    Nodes: Message, Entity, Fact, Summary, Session, Goal, Org
    Edges: HAS, NEXT, MENTIONS, REFERS_TO, SUMMARIZES
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    # Ingestion
    def upsert_message(self, message: Message) -> str:
        def _tx(tx):
            tx.run(
                """
                MERGE (o:Org {id: coalesce($org_id, "default")})
                MERGE (s:Session {id: $session_id})
                MERGE (o)-[:HAS]->(s)
                WITH o, s
                OPTIONAL MATCH (g:Goal {id: $goal_id})
                FOREACH (_ IN CASE WHEN $goal_id IS NULL THEN [] ELSE [1] END | MERGE (o)-[:HAS]->(g) MERGE (g)-[:HAS]->(s))
                MERGE (m:Message {id: $message_id})
                ON CREATE SET m.text=$text, m.ts=$ts, m.scope=$scope, m.metadata=$metadata_json
                ON MATCH SET m.text=$text, m.ts=$ts, m.scope=$scope, m.metadata=$metadata_json
                MERGE (s)-[:HAS]->(m)
                """,
                org_id=message.org_id,
                session_id=message.session_id,
                goal_id=message.goal_id,
                message_id=message.id,
                text=message.text,
                ts=int(message.ts * 1000),
                scope=message.scope,
                metadata_json=json.dumps(message.metadata or {}),
            )
        with self._driver.session() as session:
            session.execute_write(_tx)
        return message.id

    def upsert_entity(self, entity: Entity) -> str:
        def _tx(tx):
            tx.run(
                """
                MERGE (e:Entity {name: $name})
                ON CREATE SET e.id=$entity_id, e.type=$type, e.metadata=$metadata_json
                SET e.type = coalesce($type, e.type)
                """,
                name=entity.name,
                entity_id=entity.id,
                type=entity.type,
                metadata_json=json.dumps(entity.metadata or {}),
            )
        with self._driver.session() as session:
            session.execute_write(_tx)
        return entity.id

    def link_message_mentions(self, message_id: str, entity_names: Iterable[str]) -> None:
        names = list({n for n in entity_names if n})
        if not names:
            return

        def _tx(tx):
            for name in names:
                tx.run(
                    """
                    MATCH (m:Message {id: $message_id})
                    MERGE (e:Entity {name: $name})
                    ON CREATE SET e.id=toString(randomUUID())
                    MERGE (m)-[:MENTIONS]->(e)
                    """,
                    message_id=message_id,
                    name=name,
                )
        with self._driver.session() as session:
            session.execute_write(_tx)

    def upsert_fact(self, fact: Fact) -> str:
        def _tx(tx):
            tx.run(
                """
                MERGE (f:Fact {id: $id})
                ON CREATE SET f.subject=$subject, f.predicate=$predicate, f.object=$object,
                              f.confidence=$confidence, f.scope=$scope, f.ts=$ts
                ON MATCH SET f.subject=$subject, f.predicate=$predicate, f.object=$object,
                             f.confidence=$confidence, f.scope=$scope, f.ts=$ts
                WITH f
                FOREACH (_ IN CASE WHEN $source_node_id IS NULL THEN [] ELSE [1] END |
                    MATCH (n {id: $source_node_id})
                    MERGE (n)-[:REFERS_TO]->(f)
                )
                """,
                id=fact.id,
                subject=fact.subject,
                predicate=fact.predicate,
                object=fact.object,
                confidence=fact.confidence,
                scope=fact.scope,
                ts=int(fact.ts * 1000),
                source_node_id=fact.source_node_id,
            )
        with self._driver.session() as session:
            session.execute_write(_tx)
        return fact.id

    def create_summary(self, summary: Summary) -> str:
        def _tx(tx):
            tx.run(
                """
                MERGE (o:Org {id: coalesce($org_id, "default")})
                MERGE (s:Session {id: $session_id})
                MERGE (o)-[:HAS]->(s)
                CREATE (sum:Summary {id: $summary_id, text: $text, scope: $scope, ts: $ts, citations: $citations, created_by: $created_by})
                MERGE (s)-[:SUMMARIZES]->(sum)
                """,
                org_id=summary.org_id,
                session_id=summary.session_id,
                summary_id=summary.id,
                text=summary.text,
                scope=summary.scope,
                ts=int(summary.ts * 1000),
                citations=summary.citations,
                created_by=summary.created_by,
            )
        with self._driver.session() as session:
            session.execute_write(_tx)
        return summary.id

    # Edges
    def link_next(self, previous_message_id: str, next_message_id: str) -> None:
        def _tx(tx):
            tx.run(
                """
                MATCH (a:Message {id: $a}), (b:Message {id: $b})
                MERGE (a)-[:NEXT]->(b)
                """,
                a=previous_message_id,
                b=next_message_id,
            )
        with self._driver.session() as session:
            session.execute_write(_tx)

    # Retrieval helpers
    def get_session_texts(self, session_id: str, limit: Optional[int] = None) -> List[Tuple[str, str, int]]:
        query = (
            """
            MATCH (:Session {id: $session_id})-[:HAS]->(m:Message)
            RETURN m.id AS id, m.text AS text, m.ts AS ts
            ORDER BY ts ASC
            """
        )
        if limit is not None:
            query += " LIMIT $limit"
        with self._driver.session() as session:
            result = session.run(query, session_id=session_id, limit=limit)
            rows: List[Tuple[str, str, int]] = []
            for record in result:
                rows.append((record["id"], record["text"], int(record["ts"])) )
            return rows

    def get_goal_texts(self, goal_id: str, limit: Optional[int] = None) -> List[Tuple[str, str, int]]:
        query = (
            """
            MATCH (:Goal {id: $goal_id})-[:HAS]->(:Session)-[:HAS]->(m:Message)
            RETURN m.id AS id, m.text AS text, m.ts AS ts
            ORDER BY ts ASC
            """
        )
        if limit is not None:
            query += " LIMIT $limit"
        with self._driver.session() as session:
            result = session.run(query, goal_id=goal_id, limit=limit)
            rows: List[Tuple[str, str, int]] = []
            for record in result:
                rows.append((record["id"], record["text"], int(record["ts"])) )
            return rows

    def get_session_entities(self, session_id: str) -> List[Tuple[str, str]]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (:Session {id: $session_id})-[:HAS]->(m:Message)-[:MENTIONS]->(e:Entity)
                RETURN DISTINCT e.name AS name, coalesce(e.type, "") AS type
                """,
                session_id=session_id,
            )
            rows: List[Tuple[str, str]] = []
            for record in result:
                rows.append((record["name"], record["type"]))
            return rows

    def expire_ephemeral(self, now_ms: Optional[int] = None, ttl_seconds: Optional[int] = None) -> int:
        """Delete session-scoped messages older than TTL; return deleted count."""
        ttl = ttl_seconds or EPHEMERAL_TTL_SECONDS
        now_ms_val = now_ms or int(time.time() * 1000)
        cutoff = now_ms_val - ttl * 1000
        def _tx(tx):
            result = tx.run(
                """
                MATCH (m:Message {scope: 'session'})
                WHERE m.ts < $cutoff
                WITH m LIMIT 5000
                DETACH DELETE m
                RETURN count(*) AS deleted
                """,
                cutoff=cutoff,
            )
            rec = result.single()
            return int(rec["deleted"]) if rec else 0
        with self._driver.session() as session:
            deleted = session.execute_write(_tx)
        return int(deleted or 0)

    def sample_node_count(self) -> int:
        def _tx(tx):
            res = tx.run("MATCH (n) RETURN count(n) AS c")
            rec = res.single()
            return int(rec["c"]) if rec else 0
        with self._driver.session() as session:
            c = session.execute_read(_tx)
        GRAPH_NODES_GAUGE.set(c)
        return c
