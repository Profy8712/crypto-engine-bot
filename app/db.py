from sqlmodel import SQLModel, Field, create_engine, Session
from datetime import datetime

# SQLite file storage
engine = create_engine("sqlite:///logs/events.db", echo=False)


class TradeEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow)
    type: str
    symbol: str
    side: str | None = None
    price: float | None = None
    qty: float | None = None
    extra: str | None = None


def init_db():
    SQLModel.metadata.create_all(engine)


def add_event(event: TradeEvent):
    with Session(engine) as session:
        session.add(event)
        session.commit()
