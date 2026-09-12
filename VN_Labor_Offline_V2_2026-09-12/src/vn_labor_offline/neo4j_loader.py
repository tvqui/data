from __future__ import annotations
import json, os
from pathlib import Path
from .util import read_jsonl


def neo4j_properties(properties: dict) -> dict:
    """Preserve nested JSON as strings because Neo4j properties cannot contain maps."""
    result = {}
    for key, value in properties.items():
        if isinstance(value, dict) or (isinstance(value, list) and
                (any(type(item) not in (str, bool, int, float) for item in value) or
                 len({type(item) for item in value}) > 1)):
            result[key] = json.dumps(value, ensure_ascii=False)
        else:
            result[key] = value
    return result


def load_neo4j(output_dir: Path, batch_size: int=500) -> None:
    try:
        from neo4j import GraphDatabase
        from dotenv import load_dotenv
    except Exception as e:
        raise RuntimeError("Neo4j extras missing. Run uv sync --extra graph") from e
    load_dotenv()
    uri=os.getenv("NEO4J_URI","bolt://localhost:7687")
    user=os.getenv("NEO4J_USER","neo4j")
    password=os.getenv("NEO4J_PASSWORD","change_me")
    database=os.getenv("NEO4J_DATABASE","neo4j")
    nodes=list(read_jsonl(output_dir/"05_graph"/"nodes.jsonl"))
    edges=list(read_jsonl(output_dir/"05_graph"/"edges.jsonl"))
    if not nodes or not edges:
        raise RuntimeError("Graph export is missing or empty; run the offline pipeline first.")
    nodes=[{**row, 'properties':neo4j_properties(row['properties'])} for row in nodes]
    edges=[{**row, 'properties':neo4j_properties(row['properties'])} for row in edges]
    with GraphDatabase.driver(uri,auth=(user,password)) as driver:
        driver.verify_connectivity()
        driver.execute_query("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",database_=database)
        for i in range(0,len(nodes),batch_size):
            batch=nodes[i:i+batch_size]
            # Dynamic labels cannot be parameterized safely; keep a universal Entity label + semantic type property.
            driver.execute_query("""
            UNWIND $rows AS row
            MERGE (n:Entity {id: row.id})
            SET n.type = row.label
            SET n += row.properties
            """,rows=batch,database_=database)
        for i in range(0,len(edges),batch_size):
            batch=edges[i:i+batch_size]
            # APOC is used for dynamic relationship types; docker-compose enables APOC.
            driver.execute_query("""
            UNWIND $rows AS row
            MATCH (s:Entity {id: row.source}), (t:Entity {id: row.target})
            CALL apoc.merge.relationship(s, row.type, {id: row.id}, row.properties, t, {}) YIELD rel
            RETURN count(rel) AS loaded
            """,rows=batch,database_=database)
