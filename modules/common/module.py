import logging
from abc import ABC, abstractmethod
import inspect

from nio import RoomMessageText, MatrixRoom

class ModuleCannotBeDisabled(Exception):
    pass

class BotModule(ABC):
    """Abtract bot module

    A module derives from this class to process and interact on room messages. The subclass must be named `MatrixModule`.
    Just write a python file with desired command name and place it in modules. See current modules for examples.

    No need to register it anywhere else.

    Example:

        class MatrixModule(BotModule):
            async def matrix_message(self, bot, room, event):
                args = event.body.split()
                args.pop(0)

                # Echo what they said back
                await bot.send_text(room, ' '.join(args))

            def help(self):
                return 'Echoes back what user has said'

    """

    def __init__(self, name):
        self.enabled = True
        self.name = name
        self.logger = logging.getLogger("module " + self.name)

    def matrix_start(self, bot):
        """Called once on startup

        :param bot: a reference to the bot
        :type bot: Bot
        """
        self.logger.info('Starting..')

    @abstractmethod
    async def matrix_message(self, bot, room, event):
        """Called when a message is sent to room starting with !module_name

        :param bot: a reference to the bot
        :type bot: Bot
        :param room: a matrix room message
        :type room: MatrixRoom
        :param event: a handle to the event that triggered the callback
        :type event: RoomMessageText
        """
        pass

    def matrix_stop(self, bot):
        """Called once before exit

        :param bot: a reference to the bot
        :type bot: Bot
        """
        self.logger.info('Stopping..')

    async def matrix_poll(self, bot, pollcount):
        """Called every 10 seconds

        :param bot: a reference to the bot
        :type bot: Bot
        :param pollcount: the actual poll count
        :type pollcount: int
        """
        pass

    @abstractmethod
    def help(self):
        """Return one-liner help text"""
        return 'A cool hemppa module'

    def long_help(self, bot=None, room=None, event=None, args=[]):
        """Return longer help text

        Used by help module as !help modulename [args ...]
        bot, room, and event are passed to allow a module
        to give contextual help

        If not defined, falls back to short help
        """
        return self.help()

    def get_settings(self):
        """Must return a dict object that can be converted to JSON and sent to server

        :return: a dict object that can be converted to JSON
        :rtype: dict
        """
        return {'enabled': self.enabled,}

    def set_settings(self, data):
        """Load these settings. It should be the same JSON you returned in previous get_settings

        :param data: a dict object containing the settings read from the account
        :type data: dict
        """
        if data.get('enabled') is not None:
            self.enabled = data['enabled']

    def add_module_aliases(self, bot, args, force=False):
        """Add a list of aliases for this module.

        :param args: a list of strings by which this module can be called
        :type args: list
        :param force: override any existing aliases
        :type force: bool, optional
        """
        for name in args:
            if bot.modules.get(name):
                self.logger.info(f"not aliasing {name}, it is already a module")
                continue
            prev = bot.module_aliases.get(name)
            if prev == self.name:
                continue
            if prev and not force:
                self.logger.info(f"not aliasing {name}, it is already an alias for {prev}")
                continue
            if prev:
                self.logger.debug(f"overriding alias {name} for {prev}")
            bot.module_aliases[name] = self.name

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

class SubBotModule(BotModule):
    """BotModule that can handle sub commands with help system"""

    def __init__(self, name):
        super().__init__(name)
        self.sub_commands = set()
        self.sub_command_aliases = {'help': 'module_help'}

    def _load_subcommands(self):
        self.sub_commands = set([x for x in dir(self)
                                if getattr(getattr(self, x), '_is_subcommand', None)])

    def __get_command(self, name):
        name = self.sub_command_aliases.get(name) or name
        return getattr(self, name)

    async def matrix_message(self, bot, room, event):
        # Dispatch to subcommand functions:
        args = event.body.split()
        args.pop(0)
        if len(args) > 0 and args[0] in \
           self.sub_commands.union(set(self.sub_command_aliases.keys())):
            await self.__get_command(args[0])(bot, room, event, args)
            return
        else:
            await self.module_help(bot, room, event, args)

    async def module_help(self, bot, room, event, args):
        """Print this help screen"""
        if len(args) > 0 and args[0] == "help":
            args.pop(0)
        help_text = []
        if len(args) == 0:
            # Print main help:
            help_text.append("Subcommands :")
            help_text.append("---------------")
            commands = self.sub_commands.union(self.sub_command_aliases.keys())
            longest_name = len(max(commands, key=len))
            for cmd in commands:
                doc_short = self.__get_command(cmd).__doc__.splitlines()[0]
                help_text.append(f'{cmd :{longest_name}} - {doc_short}')
        else:
            # Print subcommand help:
            help_text.append(inspect.cleandoc(self.__get_command(args[0]).__doc__))
        await bot.send_text(room, "\n".join(help_text))

    @classmethod
    def subcommand(cls, func):
        """Decorator to mark BotModule methods as subcommands"""
        func._is_subcommand = True
        return func
