import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
import discord


@dataclass(frozen=True)
class UserRecord:
    user_id: int
    display_name: str
    balance: int
    created_at: str
    updated_at: str


class InsufficientBalanceError(Exception):
    pass


class Database:
    def __init__(self, db_path: str, starting_balance: int):
        self.db_path = db_path
        self.starting_balance = starting_balance
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                balance INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def ensure_user(self, user: discord.abc.User) -> UserRecord:
        now = datetime.now(timezone.utc).isoformat()
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT INTO users (user_id, display_name, balance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name=excluded.display_name,
                updated_at=excluded.updated_at
            """,
            (user.id, user.display_name, self.starting_balance, now, now),
        )
        await self._conn.commit()
        record = await self.get_user(user.id)
        assert record is not None
        return record

    async def get_user(self, user_id: int) -> Optional[UserRecord]:
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT user_id, display_name, balance, created_at, updated_at FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return UserRecord(
            user_id=row["user_id"],
            display_name=row["display_name"],
            balance=row["balance"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def settle_bet(self, user: discord.abc.User, stake: int, delta: int) -> UserRecord:
        if stake <= 0:
            raise ValueError("Stake must be greater than zero.")

        await self.ensure_user(user)
        assert self._conn is not None
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            "SELECT balance FROM users WHERE user_id = ?",
            (user.id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        balance = int(row["balance"])
        if balance < stake:
            raise InsufficientBalanceError(f"Balance {balance} < stake {stake}")

        new_balance = balance + delta
        if new_balance < 0:
            raise InsufficientBalanceError("Transaction would result in negative balance.")

        await self._conn.execute(
            "UPDATE users SET balance = ?, display_name = ?, updated_at = ? WHERE user_id = ?",
            (new_balance, user.display_name, now, user.id),
        )
        await self._conn.commit()
        record = await self.get_user(user.id)
        assert record is not None
        return record

