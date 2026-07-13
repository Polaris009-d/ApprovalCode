"""
法律知识库 — PostgreSQL 存储
"""
import json, asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LegalClause(BaseModel):
    clause_id: str = ""
    title: str = ""
    content: str = ""
    contract_types: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    source: str = ""
    chapter: str = ""
    added_at: str = ""
    updated_at: str = ""


class LegalKBCreate(BaseModel):
    clause_id: str
    title: str
    content: str
    contract_types: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    source: str = ""
    chapter: str = ""


class LegalKnowledgeBase:
    """法律知识库 — PostgreSQL 存储 (连接池)"""

    def __init__(self):
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            from ..config import settings
            dsn = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            self._pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
            async with self._pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS legal_clauses (
                        id SERIAL PRIMARY KEY, clause_id VARCHAR(128) UNIQUE NOT NULL,
                        title VARCHAR(256) NOT NULL, content TEXT NOT NULL,
                        contract_types JSONB DEFAULT '[]', tags JSONB DEFAULT '[]',
                        source VARCHAR(256) DEFAULT '', chapter VARCHAR(256) DEFAULT '',
                        added_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
                    )
                ''')
        return self._pool

    async def _acquire(self):
        pool = await self._get_pool()
        return pool.acquire()

    async def get_all(self, contract_type: str = None, keyword: str = None) -> List[LegalClause]:
        async with (await self._get_pool()).acquire() as conn:
            query = "SELECT clause_id, title, content, contract_types, tags, source, chapter, added_at, updated_at FROM legal_clauses WHERE 1=1"
            params = []
            if contract_type:
                query += f" AND contract_types::jsonb @> ${len(params)+1}::jsonb"
                params.append(json.dumps([contract_type]))
            if keyword:
                query += f" AND (title ILIKE ${len(params)+1} OR content ILIKE ${len(params)+1})"
                params.append(f"%{keyword}%")
            query += " ORDER BY clause_id"
            rows = await conn.fetch(query, *params)
            return [LegalClause(
                clause_id=r['clause_id'], title=r['title'], content=r['content'],
                contract_types=json.loads(r['contract_types']) if isinstance(r['contract_types'], str) else r['contract_types'],
                tags=json.loads(r['tags']) if isinstance(r['tags'], str) else r['tags'],
                source=r['source'] or '', chapter=r['chapter'] or '',
                added_at=r['added_at'].isoformat() if r['added_at'] else '',
                updated_at=r['updated_at'].isoformat() if r['updated_at'] else '',
            ) for r in rows]

    async def add(self, item: LegalKBCreate) -> LegalClause:
        async with (await self._get_pool()).acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM legal_clauses WHERE clause_id = $1", item.clause_id)
            if exists: raise ValueError(f"法条 '{item.clause_id}' 已存在")
            r = await conn.fetchrow(
                """INSERT INTO legal_clauses (clause_id, title, content, contract_types, tags, source, chapter)
                   VALUES ($1,$2,$3,$4::jsonb,$5::jsonb,$6,$7) RETURNING *""",
                item.clause_id, item.title, item.content, json.dumps(item.contract_types), json.dumps(item.tags), item.source, item.chapter)
            return LegalClause(clause_id=r['clause_id'], title=r['title'], content=r['content'],
                contract_types=item.contract_types, tags=item.tags, source=item.source, chapter=item.chapter,
                added_at=r['added_at'].isoformat(), updated_at=r['updated_at'].isoformat())

    async def update(self, clause_id: str, item: LegalKBCreate) -> Optional[LegalClause]:
        async with (await self._get_pool()).acquire() as conn:
            r = await conn.fetchrow(
                """UPDATE legal_clauses SET title=$1, content=$2, contract_types=$3::jsonb, tags=$4::jsonb,
                   source=$5, chapter=$6, updated_at=NOW() WHERE clause_id=$7 RETURNING *""",
                item.title, item.content, json.dumps(item.contract_types), json.dumps(item.tags), item.source, item.chapter, clause_id)
            if not r: return None
            return LegalClause(clause_id=r['clause_id'], title=r['title'], content=r['content'],
                contract_types=item.contract_types, tags=item.tags, source=item.source, chapter=item.chapter,
                added_at=r['added_at'].isoformat(), updated_at=r['updated_at'].isoformat())

    async def delete(self, clause_id: str) -> bool:
        async with (await self._get_pool()).acquire() as conn:
            result = await conn.execute("DELETE FROM legal_clauses WHERE clause_id = $1", clause_id)
            return result != "DELETE 0"

    async def search(self, contract_type: str, keywords: List[str]) -> List[Dict]:
        async with (await self._get_pool()).acquire() as conn:
            rows = await conn.fetch("SELECT * FROM legal_clauses WHERE contract_types::jsonb @> $1::jsonb", json.dumps([contract_type]))
            results = []
            for r in rows:
                ct = json.loads(r['contract_types']) if isinstance(r['contract_types'], str) else r['contract_types']
                tags = json.loads(r['tags']) if isinstance(r['tags'], str) else r['tags']
                score = 0
                for kw in keywords:
                    kwl = kw.lower()
                    if kwl in (r['title'] or '').lower(): score += 3
                    if kwl in (r['content'] or '').lower(): score += 2
                    if any(kwl in (t or '').lower() for t in tags): score += 2
                if score > 0:
                    results.append({"id": r['clause_id'], "title": r['title'], "content": r['content'],
                        "source": r['source'] or '', "chapter": r['chapter'] or '', "relevance_score": score,
                        "first_principles": r['first_principles'] or '',
                        "relationships": json.loads(r['relationships']) if r['relationships'] else [],
                        "precedent_weight": r['precedent_weight'] or 1})
            results.sort(key=lambda x: x['relevance_score'], reverse=True)
            return results

    async def stats(self) -> Dict:
        async with (await self._get_pool()).acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM legal_clauses")
            rows = await conn.fetch("SELECT source, contract_types, tags FROM legal_clauses")
            sources, type_counts, tag_counts = {}, {}, {}
            for r in rows:
                s = r['source'] or ''; sources[s] = sources.get(s, 0) + 1
                for t in (json.loads(r['contract_types']) if isinstance(r['contract_types'], str) else r['contract_types']):
                    type_counts[t] = type_counts.get(t, 0) + 1
                for t in (json.loads(r['tags']) if isinstance(r['tags'], str) else r['tags']):
                    tag_counts[t] = tag_counts.get(t, 0) + 1
            return {"total": total or 0, "by_source": sources, "by_contract_type": type_counts,
                    "top_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]}


# 全局单例
legal_kb = LegalKnowledgeBase()
