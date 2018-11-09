#!/usr/bin/env python3
# coding: utf-8

from __future__ import print_function
from time import sleep

import can.interfaces.vector
import logging
import sys


class PostFlashCheck(object):
    def __init__(self):
        # configure logging settings
        logging.basicConfig(level=logging.DEBUG, format=' %(asctime)s - %(levelname)s- %(message)s')

        try:
            self.bus2 = can.ThreadSafeBus(bustype='vector', channel=1,
                                          can_filters=[{"can_id": 0x7e1, "can_mask": 0x7e1, "extended": False}],
                                          receive_own_messages=True, bitrate=500000, app_name='InterfaceTest')
        except can.interfaces.vector.VectorError as message:
            logging.error(message)
            sys.exit()

        # Display CAN output (only 0x7E0 and 0x7E1 messages)
        self.notifier = can.Notifier(self.bus2, [can.Printer()])

    def connect(self, bus):
        msg = can.Message(arbitration_id=0x7e0,
                          data=[0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                          extended_id=False)
        self.connect_disconnect(bus, msg)
        
    # Non-short upload commands
    def connect_disconnect(self, bus, msg):
        tries = 0
        bus.send(msg)
        response_message = self.check_xcp_response(bus)
        # Retry connect/disconnect request 10 times
        while response_message is None and tries < 10:
            if msg.data[0] == 0xFF:
                logging.info("XCP slave connect retry {}".format(tries + 1))
            elif msg.data[0] == 0xFE:
                logging.info("XCP slave disconnect retry {}".format(tries + 1))
            bus.send(msg)
            response_message = self.check_xcp_response(bus)
            tries += 1
            sleep(1)

        if tries == 10:
            # Connect
            if msg.data[0] == 0xFF:
                logging.error("Failed to connect to the XCP slave!")
            # Disconnect
            else:
                logging.error("Failed to disconnect from the XCP slave!")
            sys.exit()
        else:
            command = hex(msg.data[0])

            # PID: RES
            if response_message.data[0] == 0xFF:
                # CONNECT
                if msg.data[0] == 0xFF:
                    logging.info('Connected to XCP slave through {}'.format(bus))
                # DISCONNECT
                else:
                    logging.info('Disconnected from XCP slave')
            # PID: ERR
            elif response_message.data[0] == 0xFE:
                # response indicates error, report error
                if msg.data[0] == 0xFF:
                    logging.error('Unable to connect to XCP slave through {}'.format(bus))
                else:
                    logging.error('Unable to disconnect from XCP slave through {}'.format(bus))
                sys.exit()
            # Error: XCP_ERR_CMD_UNKNOWN
            elif response_message.data[0] == 0x20:
                logging.info('Command: {} Response: XCP_ERR_CMD_UNKNOWN'.format(command))
                sys.exit()
            else:
                logging.info('Command: {} Response: {}'.format(command,
                                                               hex(response_message.data[0])))
                sys.exit()

    def get_stub_version(self, bus, msg1, msg2):
        tries = 0
        response_message = None
        while response_message is None and tries < 10:
            # StubVersion_Main
            bus.send(msg1)
            response_message = self.check_xcp_response(bus)
            tries += 1
            sleep(1)

        if tries == 10:
            logging.info('XCP slave response timeout')
        else:
            if response_message.data[0] == 0xFF:
                logging.info(
                    'Stub version (Main): {}'.format(response_message.data[1])
                )

                # StubVersion_Sub
                bus.send(msg2)
                tries = 0
                response_message = None
                while response_message is None and tries < 10:
                    # StubVersion_Main
                    bus.send(msg2)
                    response_message = self.check_xcp_response(bus)
                    tries += 1
                    sleep(1)

                if tries == 10:
                    logging.info('XCP slave response timeout')
                else:
                    if response_message.data[0] == 0xFF:
                        logging.info(
                            'Stub version (Sub):  {}'.format(response_message.data[1])
                        )
                    elif response_message.data[0] == 0x20:
                        logging.info('Command: SHORT_UPLOAD for stub version (Sub) Response: XCP_ERR_CMD_UNKNOWN')
                    else:
                        logging.info('Command: SHORT_UPLOAD for stub version (Sub) Response: {}'.format(
                            hex(response_message.data[0])))
            elif response_message.data[0] == 0x20:
                logging.info('Command: SHORT_UPLOAD for stub version (Main) Response: XCP_ERR_CMD_UNKNOWN')
            else:
                logging.info('Command: SHORT_UPLOAD for stub version (Main) Response: {}'.format(
                    hex(response_message.data[0])))

    def disconnect(self, bus):
        self.notifier.stop()

        msg = can.Message(arbitration_id=0x7e0,
                          data=[0xFE, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                          extended_id=False)
        self.connect_disconnect(bus, msg)

        bus.shutdown()

    @staticmethod
    def check_xcp_response(bus):
        # Set timeout for response message
        received_msg = bus.recv(0.05)
        while received_msg is None or received_msg.arbitration_id != 0x7E1:
            received_msg = bus.recv(0.05)
        # if received_msg.arbitration_id == 0x7E1:
        return received_msg


class PreTestCheck(object):
    # Check the following before running the Interface Test script:
    #     * CAN signals from the target (CAN Rx)
    #     <add as needed>
    def __init__(self):
        self.temp = 0


def main():
    # Update with address of StubVersion_Main
    signal_address = 0x50006a34
    message1 = can.Message(arbitration_id=0x7E0,
                           data=[0xF4, 1, 0x0, 0x0,
                                 signal_address & 0xFF,
                                 (signal_address >> 8) & 0xFF,
                                 (signal_address >> 16) & 0xFF,
                                 (signal_address >> 24) & 0xFF],
                           extended_id=False)
    # Update with address of StubVersion_Sub
    signal_address = 0x50006a38
    message2 = can.Message(arbitration_id=0x7E0,
                           data=[0xF4, 1, 0x0, 0x0,
                                 signal_address & 0xFF,
                                 (signal_address >> 8) & 0xFF,
                                 (signal_address >> 16) & 0xFF,
                                 (signal_address >> 24) & 0xFF],
                           extended_id=False)
    pfc = PostFlashCheck()
    # Connect to the XCP slave
    pfc.connect(pfc.bus2)
    # Poll the output signal every 10ms
    pfc.get_stub_version(pfc.bus2, message1, message2)
    sleep(1)
    # Disconnect from XCP slave
    pfc.disconnect(pfc.bus2)

    # ptc = PreTestCheck()


if __name__ == '__main__':
    main()

