import os
from sqlalchemy import create_engine, select, \
    Table, Column, Integer, String, ForeignKey
from sqlalchemy.orm import registry, relationship, Session
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from collections.abc import Iterable
from sqlalchemy.engine.base import Engine

from nio import RoomMessageUnknown
from modules.common.module import BotModule

MTGA_DATABASE=os.environ.get("MTGA_DATABASE", "sqlite+pysqlite:///:memory:")
db_engine = None #initialized in matrix_start()
db_mapper_registry = registry()

class MatrixModule(BotModule):
    def matrix_start(self, bot):
        global db_engine
        db_engine = create_engine(MTGA_DATABASE, echo=False, future=True)
        db_mapper_registry.metadata.bind = db_engine
        db_mapper_registry.metadata.create_all()

    async def matrix_message(self, bot, room, event):
        args = event.body.split()
        args.pop(0)

        # Echo what they said back
        self.logger.debug(f"room: {room.name} sender: {event.sender} wants an echo")
        await bot.send_text(room, '+'.join(args))

    def help(self):
        return 'Echoes back what user has said'

##################################################
## Database
##################################################

def session():
    return Session(db_engine)

@db_mapper_registry.mapped
@dataclass
class Player:
    __table__ = Table(
        "player",
        db_mapper_registry.metadata,
        Column("userID", String(255), primary_key=True),
        Column("name", String(255)),
    )
    userID: str
    name: str

    @classmethod
    def search(cls, name: str = None):
        q = select(Player)
        if name:
            q = q.where(Player.name == name)
        return q
