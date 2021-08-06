import logging
import pickle
import traceback
from pathlib import Path
from typing import List, Dict, Any

from mavsdk import telemetry
from transitions import MachineError
from transitions.extensions.asyncio import AsyncMachine

from dronebot import command as cmd
from dronebot.vocab import Vocabulary
from dronebot.voice import Voice

logger = logging.getLogger(__name__.upper())


class FlightState(object):
    """
    @DynamicAttrs
    """
    states = ['parked', 'depart', 'flight', 'inbound', 'landing']
    transitions = [
        ['recieve_clearance', 'parked',  'depart',  'clearance_valid'],
        ['recieve_clearance', 'depart',  'flight',  'clearance_valid', None, None, 'callback_takeoff'],
        ['recieve_clearance', 'flight',  'inbound', 'clearance_valid', 'direct_approach', None, 'callback_inbound'],
        ['recieve_clearance', 'flight',  'landing', 'clearance_valid', None, None, 'callback_landing'],
        ['recieve_clearance', 'inbound', 'landing', 'clearance_valid', None, None, 'callback_landing'],
        ['park', 'landing', 'parked']
    ]

    def __init__(self, command_queue, restore):
        initial = self.load() if restore else 'parked'
        self.machine = AsyncMachine(self, states=self.states, transitions=self.transitions, initial=initial, queued=True)
        self.command_queue = command_queue
        self.voice = Voice(atc="manching tower")
        self.vocab = Vocabulary()

    def clearance_valid(self, **clearance):
        logger.debug(clearance)
        valid = {
            'parked': ['route'],
            'depart': ['takeoff'],
            'flight': ['ils', 'land'],
            'inbound': ['land']
        }
        return clearance['type'] in valid.get(self.state)

    def direct_approach(self, **clearance):
        return clearance['type'] in ['land'] and self.state == 'flight'

    async def callback_takeoff(self, **clearance):
        logger.debug(clearance)
        await self.command_queue.put(cmd.Takeoff())
        # response_task = self.voice.speak("inbound MIQ, passing 3500 feet climbing FL 50")
        # await self.command_queue.put(cmd.ReportAlt(altitude=10, task=response_task))

    async def callback_inbound(self, **clearance):
        await self.command_queue.put(cmd.Direct(position=clearance['position']))
        response_task = self.voice.speak(f"Inbound {clearance['description']}")
        await self.command_queue.put(cmd.ReportPos(position=clearance['position'], task=response_task))

    async def callback_landing(self, **clearance):
        await self.command_queue.put(cmd.Land(position=clearance['position']))
        await self.command_queue.put(cmd.ReportLanded(task=self.park()))

    async def handle_commands(self, command_list: List[Dict[str, Any]]):
        condition = None
        modes = self.vocab.MODE
        for command in command_list:
            mode = command['mode'] if command else None
            if mode == modes.CONDITION:
                condition = command[str(mode)]
                self.voice.phrases.append(command['phrase'])
            if condition and command:
                delayed_task = self.update(**command)
                await self.command_queue.put(cmd.ReportPos(position=condition, task=delayed_task))
            else:
                await self.update(**command)

    async def update(self, **command):
        logger.debug(f"State: <{self.state}>")
        try:
            mode = command['mode']
            modes = self.vocab.MODE
            if mode is None:
                self.voice.phrases.append("say again")
            if mode == modes.ALTITUDE:
                await self.command_queue.put(cmd.Altitude(altitude=command[str(mode)]))
                self.voice.phrases.append(command['phrase'])
            if mode == modes.HEADING:
                await self.command_queue.put(cmd.Heading(heading=command[str(mode)]))
                self.voice.phrases.append(command['phrase'])
            if mode == modes.POSITION:
                await self.command_queue.put(cmd.Direct(position=command[str(mode)]))
                self.voice.phrases.append(command['phrase'])
            if mode == modes.REPORT:
                if command[str(mode)] == 'departure' and self.state == 'depart':
                    self.voice.phrases.append("ready for departure")
            if mode == modes.CONTACT:
                Voice.atc = command[str(mode)]
                self.voice.phrases.append(command['phrase'])
            if mode == modes.CLEARANCE:
                if self.clearance_valid(**command[str(mode)]):
                    await self.recieve_clearance(**command[str(mode)])
                    self.voice.phrases.append(command['phrase'])
                else:
                    self.voice.phrases.append("Unable")
        except MachineError as e:
            logger.error(e)
            logger.debug(traceback.format_exc())
            self.voice.phrases.append("Unable")

    def save(self):
        logger.debug("Saving flight state")
        with open(Path('saves/flight_state.p').absolute(), 'wb+') as save_handle:
            pickle.dump(self.state, save_handle)

    def load(self):
        logger.debug("Loading flight state")
        with open(Path('saves/flight_state.p').absolute(), 'rb') as load_handle:
            return pickle.load(load_handle)
