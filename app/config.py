from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val


@dataclass
class SeatPair:
    section: str
    row: str
    seat_from: int
    seat_to: int
    face_value: float
    list_price: float

    @property
    def seat_count(self) -> int:
        return self.seat_to - self.seat_from + 1

    def __str__(self) -> str:
        return f"Section {self.section} Row {self.row} seats {self.seat_from}-{self.seat_to}"


class Settings:
    # Discord
    discord_bot_token: str = _require("DISCORD_BOT_TOKEN")
    discord_user_id: int = int(_require("DISCORD_USER_ID"))

    # Seat pairs — both are listed independently on Ticketmaster
    seat_pairs: list[SeatPair] = [
        SeatPair(
            section=os.getenv("SEAT1_SECTION", ""),
            row=os.getenv("SEAT1_ROW", ""),
            seat_from=int(os.getenv("SEAT1_FROM", "1")),
            seat_to=int(os.getenv("SEAT1_TO", "2")),
            face_value=float(os.getenv("SEAT1_FACE_VALUE", "0")),
            list_price=float(os.getenv("SEAT1_LIST_PRICE", "0")),
        ),
        SeatPair(
            section=os.getenv("SEAT2_SECTION", ""),
            row=os.getenv("SEAT2_ROW", ""),
            seat_from=int(os.getenv("SEAT2_FROM", "1")),
            seat_to=int(os.getenv("SEAT2_TO", "2")),
            face_value=float(os.getenv("SEAT2_FACE_VALUE", "0")),
            list_price=float(os.getenv("SEAT2_LIST_PRICE", "0")),
        ),
    ]

    # Pricing
    weekend_premium: float = float(os.getenv("WEEKEND_PREMIUM", "0"))

    # App
    database_path: str = os.getenv("DATABASE_PATH", "bulls.db")
    schedule_csv_path: str = os.getenv("SCHEDULE_CSV_PATH", "schedule.csv")

    # Dashboard
    dashboard_host: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    dashboard_port: int = int(os.getenv("DASHBOARD_PORT", "8080"))

    # Ticketmaster — listing is a manual action (no public seller API), so this
    # is just the link the prep message points you to. Defaults to the account
    # "My Events" page; override once we confirm a working per-event sell deep
    # link against the real account during testing.
    ticketmaster_sell_url: str = os.getenv(
        "TICKETMASTER_SELL_URL", "https://www.ticketmaster.com/myevents"
    )


settings = Settings()
