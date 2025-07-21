import asyncio
from collections import deque
import importlib
from pathlib import Path
from typing import Any, Deque, Generic, Optional, TypeVar
import json
import aiosqlite
from port_ocean.runtime_vars import workers

from datetime import datetime, timedelta, timezone

from .abstract_queue import AbstractQueue
import cloudpickle  # type: ignore

T = TypeVar("T")


# ──────────────────────── (de)serialisation helpers ─────────────────────── #


def smart_dumps(obj: object) -> bytes:
    dump = getattr(obj, "to_dict", None)
    if callable(dump):  # Pydantic / dataclass‑like
        cls = obj.__class__
        meta = {
            "__CUSTOM_DATACLASS__": True,
            "__module__": cls.__module__,
            "__qualname__": cls.__qualname__,
            "data": dump(),
        }
        return json.dumps(meta, separators=(",", ":")).encode()
    return cloudpickle.dumps(obj)  # type: ignore


def smart_loads(blob: bytes) -> Any:
    if blob[:1] == b"{" and b"__CUSTOM_DATACLASS__" in blob[:40]:
        meta = json.loads(blob.decode())
        if meta.get("__CUSTOM_DATACLASS__"):
            mod = importlib.import_module(meta["__module__"])
            cls = getattr(mod, meta["__qualname__"])
            return cls(**meta["data"])
    return cloudpickle.loads(blob)


# ─────────────────────────────────  Queue  ──────────────────────────────── #


class DiskQueue(AbstractQueue[T], Generic[T]):
    """
    Crash‑safe FIFO queue backed by SQLite **with an async connection pool**.

    put()      -> INSERTs item (status = 0)
    get()      -> atomically "claims" oldest status = 0 row  (status → 1)
    commit()   -> DELETEs the claimant's own pending row
    teardown() -> waits for drain; closes every pooled connection
    """

    _DDL = """
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous   = NORMAL;
    CREATE TABLE IF NOT EXISTS queue(
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        payload BLOB    NOT NULL,   -- pickled item
        status  INTEGER NOT NULL DEFAULT 0,
        expired_date  DATETIME NOT NULL
    );
    """

    def __init__(
        self,
        name: str,
        *,
        poll_interval: float = 0.1,
        dir_: str | Path = "queues",
        pool_size: int | None = None,  # NEW
    ) -> None:
        dir_path = Path(dir_)
        dir_path.mkdir(parents=True, exist_ok=True)
        self._db_path = dir_path / self._route_to_filename(name)
        self._poll_interval = poll_interval

        # ───── connection‑pool state ─────
        self._pool: Optional[asyncio.Queue[aiosqlite.Connection]] = None
        self._pool_size = int(pool_size or workers or 2)
        self._all_conns: list[aiosqlite.Connection] = []

        # ───── per‑consumer state ─────
        self._pending: Deque[int] = deque()

    # ───────────────────────── helpers ───────────────────────── #

    @staticmethod
    def _route_to_filename(route: str) -> str:
        safe = route.replace("/", "#")
        return f"{safe}#.sqlite"

    # ─────────────────────── infra / pooling ─────────────────── #

    async def _init_pool(self) -> None:
        if self._pool is not None:
            return  # already initialised

        self._pool = asyncio.Queue(self._pool_size)

        # create first connection, run DDL once
        first = await aiosqlite.connect(self._db_path)
        await first.executescript(self._DDL)
        first.row_factory = aiosqlite.Row
        await self._pool.put(first)
        self._all_conns.append(first)

        # create the remaining pooled connections
        for _ in range(self._pool_size - 1):
            conn = await aiosqlite.connect(self._db_path)
            # only PRAGMA, table already exists
            await conn.executescript(
                "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;"
            )
            conn.row_factory = aiosqlite.Row
            await self._pool.put(conn)
            self._all_conns.append(conn)

    async def _acquire(self) -> aiosqlite.Connection:
        await self._init_pool()
        return await self._pool.get()  # type: ignore[arg-type]

    async def _release(self, conn: aiosqlite.Connection) -> None:
        # Return connection to the pool for reuse
        await self._pool.put(conn)  # type: ignore[arg-type]

    # ───────────────────── public queue API ─────────────────── #

    async def put(self, item: T) -> None:
        conn = await self._acquire()
        try:
            blob = smart_dumps(item)
            await conn.execute(
                "INSERT INTO queue(payload, expired_date) VALUES (?, ?)",
                (
                    blob,
                    datetime.now(timezone.utc) + timedelta(seconds=30),
                ),
            )
            await conn.commit()
        finally:
            await self._release(conn)

    async def get(self) -> T:
        while True:
            conn = await self._acquire()
            try:
                await conn.execute(
                    """
                    WITH cte_x AS (
                        SELECT id
                        FROM   queue
                        WHERE  status = 1 and unixepoch(CURRENT_TIMESTAMP) -unixepoch(expired_date) > 0
                    )
					UPDATE queue
                       SET status = 0
                     WHERE id IN (SELECT id FROM cte_x)
                    """
                )
                async with conn.execute(
                    """
					 WITH cte AS (
                        SELECT id, payload
                        FROM   queue
                        WHERE  status = 0
                        ORDER  BY id
                        LIMIT  1
                    )
                    UPDATE queue
                       SET status = 1
                     WHERE id IN (SELECT id FROM cte)
                    RETURNING id, payload
                    """
                ) as cursor:
                    row = await cursor.fetchone()

                if row is not None:  # successfully claimed a row
                    await conn.commit()
                    self._pending.append(row["id"])
                    return smart_loads(row["payload"])
            finally:
                await self._release(conn)

            # queue empty → back off (non‑blocking sleep)
            await asyncio.sleep(self._poll_interval)

    async def commit(self) -> None:
        if not self._pending:
            raise RuntimeError("commit() called more times than get()")

        row_id = self._pending.popleft()
        conn = await self._acquire()
        try:
            await conn.execute("DELETE FROM queue WHERE id = ?", (row_id,))
            await conn.commit()
        finally:
            await self._release(conn)

    async def teardown(self) -> None:
        # wait until no outstanding work
        while True:
            conn = await self._acquire()
            try:
                async with conn.execute("SELECT COUNT(*) FROM queue") as cur:
                    row = await cur.fetchone()
                    assert row
                    (remaining,) = row
                if remaining == 0 and not self._pending:
                    break
            finally:
                await self._release(conn)
            await asyncio.sleep(self._poll_interval)

        # close every connection in the pool
        for conn in self._all_conns:
            await conn.close()

        self._pool = None
        self._all_conns.clear()
