import json
import os
import re
import sqlite3
import tempfile
from hashlib import sha1
from typing import Any, AsyncGenerator, Iterable, Protocol
from urllib.parse import urlparse

import httpx
import ijson  # type: ignore[import-untyped]

import port_ocean.context.ocean as ocean_context


class TableNameResolver(Protocol):
    def resolve(self, endpoint: str) -> str: ...


class ColumnProjector(Protocol):
    def project(self, item: dict[str, Any]) -> dict[str, str | None]: ...

    @property
    def output_columns(self) -> list[str]: ...


class StreamStore(Protocol):
    def insert_items(self, items: Iterable[dict[str, Any]]) -> None: ...

    def fetch_items_after(
        self, row_id: int, batch_size: int
    ) -> list[tuple[int, dict[str, Any]]]: ...

    def cleanup(self) -> None: ...


class EndpointTableNameResolver:
    def resolve(self, endpoint: str) -> str:
        parsed = urlparse(endpoint)
        endpoint_path = parsed.path if parsed.path else endpoint
        normalized = endpoint_path.strip("/") or "root"
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
        if not normalized:
            normalized = "root"
        if normalized[0].isdigit():
            normalized = f"endpoint_{normalized}"
        suffix = sha1(endpoint.encode("utf-8")).hexdigest()[:8]
        return f"{normalized}_{suffix}"


class JsonColumnProjector:
    def __init__(self, selected_columns: list[str]) -> None:
        if not selected_columns:
            raise ValueError("selected_columns must not be empty")
        self._selected_columns = selected_columns

    @property
    def output_columns(self) -> list[str]:
        return self._selected_columns

    def project(self, item: dict[str, Any]) -> dict[str, str | None]:
        projected: dict[str, str | None] = {}
        for column in self._selected_columns:
            value = self._extract_dot_path(item, column)
            projected[column] = self._to_storage_value(value)
        return projected

    def _extract_dot_path(self, item: dict[str, Any], path: str) -> Any:
        current: Any = item
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    def _to_storage_value(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return json.dumps(value, sort_keys=True)


class SqliteStreamStore:
    def __init__(
        self,
        table_name: str,
        projector: ColumnProjector,
        db_directory: str | None = None,
        include_raw_json: bool = False,
    ) -> None:
        self._projector = projector
        self._table_name = table_name
        self._include_raw_json = include_raw_json
        self._column_to_sql = self._build_sql_columns(projector.output_columns)
        self._sql_to_column = {v: k for k, v in self._column_to_sql.items()}

        if db_directory is None:
            db_directory = ocean_context.ocean.config.streaming.location
        os.makedirs(db_directory, exist_ok=True)
        temp = tempfile.NamedTemporaryFile(
            mode="wb", suffix=".db", dir=db_directory, delete=False
        )
        self._db_path = temp.name
        temp.close()
        self._connection = sqlite3.connect(self._db_path)
        self._create_table()

    @property
    def db_path(self) -> str:
        return self._db_path

    def insert_items(self, items: Iterable[dict[str, Any]]) -> None:
        column_sql_names = list(self._column_to_sql.values())
        insert_columns = ",".join(f'"{column}"' for column in column_sql_names)
        placeholders = ",".join("?" for _ in column_sql_names)
        if self._include_raw_json:
            insert_columns = f"{insert_columns},raw_json"
            placeholders = f"{placeholders},?"

        query = (
            f'INSERT INTO "{self._table_name}" ({insert_columns}) VALUES ({placeholders})'
        )
        payload: list[tuple[Any, ...]] = []
        for item in items:
            projected = self._projector.project(item)
            values = [projected[column] for column in self._projector.output_columns]
            if self._include_raw_json:
                values.append(json.dumps(item, sort_keys=True))
            payload.append(tuple(values))

        if payload:
            self._connection.executemany(query, payload)
            self._connection.commit()

    def fetch_items_after(
        self, row_id: int, batch_size: int
    ) -> list[tuple[int, dict[str, Any]]]:
        column_sql_names = list(self._column_to_sql.values())
        selected_columns = ",".join(f'"{column}"' for column in column_sql_names)
        cursor = self._connection.execute(
            f'SELECT row_id, {selected_columns} FROM "{self._table_name}" WHERE row_id > ? ORDER BY row_id ASC LIMIT ?',
            (row_id, batch_size),
        )
        rows = cursor.fetchall()

        results: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            row_identifier = int(row[0])
            values = row[1:]
            item: dict[str, Any] = {}
            for index, value in enumerate(values):
                sql_name = column_sql_names[index]
                item[self._sql_to_column[sql_name]] = value
            results.append((row_identifier, item))
        return results

    def cleanup(self) -> None:
        self._connection.close()
        try:
            os.remove(self._db_path)
        except FileNotFoundError:
            pass

    def _create_table(self) -> None:
        sql_columns = [f'"{name}" TEXT' for name in self._column_to_sql.values()]
        if self._include_raw_json:
            sql_columns.append("raw_json TEXT")
        columns_sql = ",".join(sql_columns)
        self._connection.execute(
            f'CREATE TABLE "{self._table_name}" (row_id INTEGER PRIMARY KEY AUTOINCREMENT, {columns_sql})'
        )
        self._connection.commit()

    def _build_sql_columns(self, columns: list[str]) -> dict[str, str]:
        mappings: dict[str, str] = {}
        used: set[str] = set()
        for column in columns:
            base = re.sub(r"[^a-zA-Z0-9]+", "_", column).strip("_").lower() or "col"
            if base[0].isdigit():
                base = f"col_{base}"
            candidate = base
            if candidate in used:
                suffix = sha1(column.encode("utf-8")).hexdigest()[:8]
                candidate = f"{base}_{suffix}"
            used.add(candidate)
            mappings[column] = candidate
        return mappings


class SqliteJsonStream:
    def __init__(
        self,
        response: httpx.Response,
        stream_store: StreamStore,
    ) -> None:
        self._response = response
        self._stream_store = stream_store

    async def stream_json(
        self,
        target_items: str,
        chunk_size: int | None = None,
        max_buffer_size_mb: int | None = None,
        output_batch_size: int = 500,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if chunk_size is None:
            chunk_size = ocean_context.ocean.config.streaming.chunk_size
        if max_buffer_size_mb is None:
            max_buffer_size_mb = ocean_context.ocean.config.streaming.max_buffer_size_mb

        current_buffer_size = 0
        last_yielded_row_id = 0
        events = ijson.sendable_list()
        parser = ijson.items_coro(events, target_items)

        try:
            async for chunk in self._response.aiter_bytes(chunk_size=chunk_size):
                if not chunk:
                    continue
                parser.send(chunk)
                current_buffer_size += len(chunk)
                if events:
                    self._stream_store.insert_items(events)
                    events.clear()

                if current_buffer_size >= max_buffer_size_mb:
                    async for last_yielded_row_id, batch in self._yield_available_rows(
                        last_yielded_row_id, output_batch_size
                    ):
                        yield batch
                    current_buffer_size = 0

            if events:
                self._stream_store.insert_items(events)
                events.clear()

            async for _, batch in self._yield_available_rows(
                last_yielded_row_id, output_batch_size
            ):
                yield batch
        finally:
            await self._response.aclose()
            self._stream_store.cleanup()

    async def _yield_available_rows(
        self, last_row_id: int, batch_size: int
    ) -> AsyncGenerator[tuple[int, list[dict[str, Any]]], None]:
        cursor = last_row_id
        while True:
            rows = self._stream_store.fetch_items_after(cursor, batch_size)
            if not rows:
                break
            cursor = rows[-1][0]
            yield cursor, [item for _, item in rows]
