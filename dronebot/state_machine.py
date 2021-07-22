from transitions import Machine, MachineError
from dronebot.vocabulary import Vocabulary
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
        ['park', 'landing', 'parked'],
        ['modify_route', 'flight', 'flight', None, None, None, 'callback_command']
    ]

    def __init__(self, parser):
        self.machine = Machine(self, states=self.states, transitions=self.transitions, initial='parked', queued=True)
        self.parser = parser
        self.vocab = Vocabulary()

    def clearance_valid(self, args):
        valid = {
            'parked': ['flight planned route'],
            'depart': ['takeoff'],
            'flight': ['ils', 'land'],
            'inbound': ['land']
        }
        return args[0] in valid.get(self.state)

    def direct_approach(self, args):
        return args[0] in ['land'] and self.state == 'flight'

    def callback_takeoff(self, args):
        self.parser.command_list.append((self.vocab.MODE.TAKEOFF, None))
        self.parser.handle_response_queue()
        self.parser.handle_response("inbound MIQ, passing 3500 feet climbing FL 50")
        self.parser.handle_response_queue(True)

    def callback_inbound(self, args):
        self.parser.command_list.append((self.vocab.MODE.POSITION, args[1]))

    def callback_landing(self, args):
        self.parser.command_list.append((self.vocab.MODE.LAND, args[1]))

    def callback_command(self, args):
        self.parser.command_list.append(args)

    def update(self, command, mode, args):
        logger.debug(f"State: <{self.state.uppercase()}>")
        try:
            modes = self.vocab.MODE
            if mode in [modes.ALTITUDE, modes.HEADING, modes.POSITION]:
                self.modify_route((mode, args))
                self.parser.handle_response(command)
            if mode == modes.REPORT:
                if args == 'departure' and self.state == 'depart':
                    self.parser.handle_response('ready for departure')
            if mode == modes.CONTACT:
                self.parser.atc = args
                self.parser.handle_response(command)
            if mode == modes.CLEARANCE:
                if self.clearance_valid(args):
                    self.parser.handle_response(command)
                    self.recieve_clearance(args)
                else:
                    self.parser.handle_response("Unable")
        except MachineError as e:
            logger.error(e)
            self.parser.handle_response("Unable")
