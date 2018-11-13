#!/usr/bin/env python3
# coding: utf-8

from __future__ import print_function
from time import sleep

import can.interfaces.vector
import logging
import sys
import os
import time

logging.basicConfig(filename='run.log', filemode='w', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class PostFlashPreTestCheck(object):
    def __init__(self, variant):
        self.variant = variant
        self.message_list = []

        try:
            self.bus2 = can.ThreadSafeBus(bustype='vector', channel=1,
                                          can_filters=[{"can_id": 0x7e1, "can_mask": 0x7e1, "extended": False}],
                                          receive_own_messages=True, bitrate=500000, app_name='CANoe')
        except can.interfaces.vector.VectorError as message:
            # logging.error(message)
            print(message)
            sys.exit()

        # # Display CAN output (only 0x7E0 and 0x7E1 messages)
        # self.notifier = can.Notifier(self.bus2, [can.Printer()])

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

        logging.info('Checking for the stub version..')
        print('Checking for the stub version..')

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
                print('Stub version (Main): {}'.format(response_message.data[1]))

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
                        print('Stub version (Sub):  {}'.format(response_message.data[1]))
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
        # self.notifier.stop()
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

    def create_message_list(self):
        """Create a list of dictionaries of CAN message the following information:
            can_ch - channel of the CAN message
            can_id - ID of the CAN message
            cycle  - transmission cycle of the CAN message in milliseconds

            Updates self.message_list
        """
        for root, dirs, files in os.walk(".\\DBC"):
            for file in files:
                if file.endswith(".dbc"):
                    if root.find(self.variant) != -1:
                        # CAN 1
                        if file.find('LOCAL1') != -1:
                            dbc_file = open(os.path.join(root, file), 'r')
                            for line in dbc_file:
                                if line.find('BO_ ') != -1 and line.find('EYE') != -1:
                                    data = line.split()
                                    self.message_list.append({'can_ch': 1, 'can_id': int(data[1]), 'cycle': 0})

                                if line.find('BA_ ') != -1 and line.find('GenMsgCycleTime') != -1:
                                    data = line.split()
                                    for index in range(len(self.message_list)):
                                        if self.message_list[index]['can_ch'] == 1 and self.message_list[index]['can_id'] == int(data[3]):
                                            if int(data[4][:-1]) == 0:
                                                self.message_list.remove(self.message_list[index])
                                            else:
                                                self.message_list[index]['cycle'] = int(data[4][:-1])
                                            break

                            dbc_file.close()
                        # CAN 2
                        elif file.find('LOCAL2') != -1:
                            dbc_file = open(os.path.join(root, file), 'r')
                            for line in dbc_file:
                                if line.find('BO_ ') != -1 and line.find('EYE') != -1:
                                    data = line.split()
                                    self.message_list.append({'can_ch': 2, 'can_id': int(data[1]), 'cycle': 0})

                                if line.find('BA_ ') != -1 and line.find('GenMsgCycleTime') != -1:
                                    data = line.split()
                                    for index in range(len(self.message_list)):
                                        if self.message_list[index]['can_ch'] == 2 and self.message_list[index]['can_id'] == int(data[3]):
                                            if int(data[4][:-1]) == 0:
                                                self.message_list.remove(self.message_list[index])
                                            else:
                                                self.message_list[index]['cycle'] = int(data[4][:-1])
                                            break

                            dbc_file.close()
                        # CAN 3
                        elif file.find('SA') != -1:
                            dbc_file = open(os.path.join(root, file), 'r')
                            for line in dbc_file:
                                if line.find('BO_ ') != -1 and line.find('EYE') != -1:
                                    data = line.split()
                                    self.message_list.append({'can_ch': 3, 'can_id': int(data[1]), 'cycle': 0})

                                if line.find('BA_ ') != -1 and line.find('GenMsgCycleTime') != -1:
                                    data = line.split()
                                    for index in range(len(self.message_list)):
                                        if self.message_list[index]['can_ch'] == 3 and self.message_list[index]['can_id'] == int(data[3]):
                                            if int(data[4][:-1]) == 0:
                                                self.message_list.remove(self.message_list[index])
                                            else:
                                                self.message_list[index]['cycle'] = int(data[4][:-1])
                                            break

                            dbc_file.close()
                        # CAN 4
                        elif file.find('PU') != -1:
                            dbc_file = open(os.path.join(root, file), 'r')
                            for line in dbc_file:
                                if line.find('BO_ ') != -1 and line.find('EYE') != -1:
                                    data = line.split()
                                    self.message_list.append({'can_ch': 4, 'can_id': int(data[1]), 'cycle': 0})

                                if line.find('BA_ ') != -1 and line.find('GenMsgCycleTime') != -1:
                                    data = line.split()
                                    for index in range(len(self.message_list)):
                                        if self.message_list[index]['can_ch'] == 4 and self.message_list[index]['can_id'] == int(data[3]):
                                            if int(data[4][:-1]) == 0:
                                                self.message_list.remove(self.message_list[index])
                                            else:
                                                self.message_list[index]['cycle'] = int(data[4][:-1])
                                            break

                            dbc_file.close()
                        else:
                            pass

    def wait_for_messages(self, can_ch):
        """Wait for CAN messages in the bus specified

        Arguments:
            can_ch - CAN channel to check for CAN messages

        Return:
            status
                0 - Received all expected messages
                1 - Incomplete messages received
                2 - No message received
        """
        bus = can.interface.Bus(bustype='vector', channel=can_ch-1,
                                receive_own_messages=False, bitrate=500000, app_name='CANoe')

        # CAN logger
        asc_file = 'CAN'+str(can_ch)+'_log.asc'
        can_log = open(asc_file, 'w+')
        asc_writer = can.ASCWriter(asc_file)
        notifier = can.Notifier(bus, [asc_writer])
        message_count = 0
        check_count = 0
        message_status = []

        print('Checking CAN messages in CAN channel {}'.format(can_ch))

        for index in range(len(self.message_list)):
            if self.message_list[index]['can_ch'] == can_ch:
                can_id = self.message_list[index]['can_id']
                message_count += 1
                start_s = time.time()
                found = False
                while time.time() < start_s + 1.0:
                    received_message = bus.recv()
                    if received_message.arbitration_id == can_id:
                        message_status.append({'can_ch': can_ch, 'can_id': can_id, 'status': 'Received'})
                        found = True
                        check_count += 1
                        logging.info('CAN ID {}: Received'.format(str(hex(can_id))[2:5].upper()))
                        break

                if not found:
                    message_status.append({'can_ch': can_ch, 'can_id': can_id, 'status': 'Not Received'})
                    logging.info('CAN ID {}: Not Received'.format(str(hex(can_id))[2:5].upper()))

        # for index in range(len(message_status)):
        #     print('{}'.format(hex(message_status[index]['can_id'])), message_status[index]['status'])

        can_log.close()
        # logging.shutdown()
        notifier.stop()
        asc_writer.stop()
        bus.shutdown()

        if check_count == 0:
            print('Result: Did not receive any message from CAN channel {}'.format(can_ch))
            return 2
        elif check_count < message_count:
            print('Result: {} of {} messages received from CAN channel {}'.format(check_count, message_count,
                                                                                  can_ch))
            return 1
        elif check_count == message_count:
            print('Result: All expected messages received from CAN channel {}'.format(can_ch))
            return 0
        else:
            pass

    def shutdwon_logging(self):
        logging.shutdown()
        print('Please check the run.log file')


def main():
    # How to dynamically update the addresses of StubVersion_Main and StubVersion_Sub???
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
    pfptc = PostFlashPreTestCheck('GC7')
    # Connect to the XCP slave
    pfptc.connect(pfptc.bus2)
    # Poll the output signal every 10ms
    pfptc.get_stub_version(pfptc.bus2, message1, message2)
    sleep(1)
    # Disconnect from XCP slave
    pfptc.disconnect(pfptc.bus2)

    pfptc.create_message_list()
    pfptc.wait_for_messages(1)
    pfptc.wait_for_messages(2)
    pfptc.wait_for_messages(3)
    pfptc.wait_for_messages(4)
    pfptc.shutdwon_logging()


if __name__ == '__main__':
    main()

