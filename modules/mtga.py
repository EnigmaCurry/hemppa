import os
from sqlalchemy import create_engine, select, \
    Table, Column, Integer, String, ForeignKey
from sqlalchemy.orm import registry, relationship, Session
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from collections.abc import Iterable
from sqlalchemy.engine.base import Engine
from sqlalchemy_schemadisplay import create_schema_graph

from nio import RoomMessageUnknown
from modules.common.module import BotModule, SubBotModule

MTGA_DATABASE=os.environ.get("MTGA_DATABASE", "sqlite+pysqlite:///:memory:")
db_engine = None #initialized in matrix_start()
db_mapper_registry = registry()

class MatrixModule(SubBotModule):
    def help(self):
        """matrix module API help"""
        return 'MTGA game bot'

    def matrix_start(self, bot):
        global db_engine
        db_engine = create_engine(MTGA_DATABASE, echo=False, future=True)
        db_mapper_registry.metadata.bind = db_engine
        db_mapper_registry.metadata.create_all()
        self.sub_command_aliases.update({'players':'player'})
        ## Load all sub commands decorated with @subcommand:
        self._load_subcommands()

    @SubBotModule.subcommand
    async def schema(self, bot, room, event, args):
        """Make an image showing the database schema"""
        img = make_db_diagram()
        await bot.upload_and_send_image(room, img, text="Database schema",
                                        blob=True, blob_content_type="image/png")

    @SubBotModule.subcommand
    async def player(self, bot, room, event, args):
        """Manage players
        !mtga player list                 : List all registered players
        !mtga player register [nickname]  : Register yourself as [nickname]
        """
        if len(args) > 1:
            if args[1] == "list":
                with session() as s:
                    res = tuple(s.execute(Player.search(room)))
                    if len(res) > 0:
                        player_list = ", ".join([p.name for p in res[0]])
                    else:
                        player_list = "None"
                await bot.send_text(room, f"Players in {room.name}: {player_list}")
            elif args[1] == "register":
                user = bot.client.rooms[room.room_id].users[event.sender]
                try:
                    register_player(user, str(room))
                    await bot.send_text(room, f"Registered player: {user.display_name}")
                except PlayerAlreadyRegistered:
                    await bot.send_text(room, f"Player is already registered: {user.display_name}")
        else:
            await self.module_help(bot, room, event, args)

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
        Column("user_id", String(255), primary_key=True),
        Column("room", String(255), primary_key=True),
        Column("name", String(255)),
    )
    user_id: str
    room: str
    name: str

    @classmethod
    def search(cls, room, name: str = None):
        q = select(Player)
        if name:
            q = q.where(Player.name == name and Player.room == room)
        return q

class PlayerAlreadyRegistered(Exception):
    pass

def register_player(user, room):
    with session() as s:
        existing = tuple(s.execute(select(Player).where(Player.user_id == user.user_id and Player.room == room)))
        if len(existing) < 1:
            player = Player(user.user_id, room, user.display_name)
            s.add(player)
            s.commit()
        else:
            raise PlayerAlreadyRegistered()

def make_db_diagram():
    graph = create_schema_graph(metadata=db_mapper_registry.metadata,
                                show_datatypes=False,
                                show_indexes=False,
                                rankdir="LR",
                                concentrate=False)
    return graph.create_png()

