import os, re, random
from sqlalchemy import create_engine, select, update, \
    Table, Column, Integer, String, ForeignKey
from sqlalchemy.orm import registry, relationship, Session
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from collections.abc import Iterable
from sqlalchemy.engine.base import Engine

from nio import RoomMessageUnknown
from modules.common.module import BotModule

ROLL_DATABASE=os.environ.get("ROLL_DATABASE", "sqlite+pysqlite:///:memory:")
db_engine = None #initialized in matrix_start()
db_mapper_registry = registry()

class MatrixModule(BotModule):
    def matrix_start(self, bot):
        global db_engine
        db_engine = create_engine(ROLL_DATABASE, echo=False, future=True)
        db_mapper_registry.metadata.bind = db_engine
        db_mapper_registry.metadata.create_all()

    async def matrix_message(self, bot, room, event):
        user = bot.client.rooms[room.room_id].users[event.sender]
        args = event.body.split()
        args.pop(0)

        # Roll the specified dice
        self.logger.debug(f"room: {room.name} sender: {event.sender} "
                          "wants dice rolled: {args}")
        dice = ' '.join(args)
        if not dice:
            last_roll = get_last_roll(user.user_id)
            if last_roll:
                dice = last_roll
            else:
                dice = "1d6"

        try:
            total, results = roll(dice)
        except:
            await bot.send_text(room, "Invalid dice notation")
            return
        update_last_roll(user.user_id, dice)
        await bot.send_text(room, f"@{user.display_name} {dice} = {pretty_results(results, total)}")

    def help(self):
        return 'Echoes back what user has said'

def roll(dice):
    die_pattern = re.compile("^(?P<count>\\d*)d(?P<value>\\d+)((?P<mod>[\-\+])(?P<mod_val>\\d+))?$")
    results = []
    total = 0
    for die in re.split("\s+", dice.replace("\\s", "")):
        if die == "+":
            continue
        search = die_pattern.search(die)
        count = search.group("count")
        count = int(count) if count else 1
        value = int(search.group("value"))
        mod_val = int(search.group("mod_val") or "0")
        if mod_val > 0 and search.group("mod") == "-":
            mod_val = -1 * mod_val
        res = []
        for d in range(count):
            res.append(random.randrange(value) + 1)
        results.append(res)
        total += sum(res) + mod_val
    if len(results) == 1:
        results = results[0]
    return (total, results)

def pretty_results(results, total):
    if len(results) > 1:
        results = '+'.join((str(x) for x in results))
        results = results.replace("[","(").replace("]",")").replace(", ","+")
        results += f" = {total}"
    else:
        results = results[0]
    return results

##################################################
## Database
##################################################

def session():
    return Session(db_engine)

@db_mapper_registry.mapped
@dataclass
class UserRoll:
    __table__ = Table(
        "user_roll",
        db_mapper_registry.metadata,
        Column("user_id", String(255), primary_key=True),
        Column("last_roll", String(255)),
    )
    user_id: str
    last_roll: str

    @classmethod
    def get(cls, user_id: str):
        q = select(UserRoll).where(UserRoll.user_id == user_id)
        return q

def get_last_roll(user_id):
    with session() as s:
        user_roll = s.execute(UserRoll.get(user_id)).first()
        if user_roll:
            print(user_roll[0])
            return user_roll[0].last_roll
        else:
            return None

def update_last_roll(user_id, last_roll):
    with session() as s:
        user_roll = s.execute(UserRoll.get(user_id)).first()
        if user_roll:
            user_roll = user_roll[0]
        else:
            user_roll = UserRoll(user_id, last_roll)
        user_roll.last_roll = last_roll
        s.add(user_roll)
        s.commit()

