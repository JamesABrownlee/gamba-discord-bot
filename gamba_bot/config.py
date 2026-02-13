import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    database_path: str
    starting_balance: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise ValueError("DISCORD_TOKEN is required.")

        database_path = os.getenv("DATABASE_PATH", "./data/gamba.db")
        starting_balance = int(os.getenv("STARTING_BALANCE", "1000"))
        return cls(
            discord_token=token,
            database_path=database_path,
            starting_balance=starting_balance,
        )
