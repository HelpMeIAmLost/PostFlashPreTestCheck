#!/usr/bin/env python3
# coding: utf-8

from __future__ import print_function
from time import sleep
from pathlib import Path
from common_util import *

import can.interfaces.vector
import logging
import sys
import os
import time

logging.basicConfig(filename='run.log', filemode='w', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class PostFlashPreTestCheck(object):
    def __init__(self, variant, map_folder, dbc_folder):
        """
        Initialize class variables
        :param variant: Vehicle variant
        """
        self.variant = str(variant).upper()
        self.dbc_folder = Path(dbc_folder)
        self.map_folder = Path(map_folder)
        self.message_list = []
        self.message_status = {}

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

    def connect(self, bus=None):
        msg = can.Message(arbitration_id=0x7e0,
                          data=[0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                          extended_id=False)
        self.connect_disconnect(bus, msg)

        conn = create_connection("interface.db")
        if conn is not None:
            # Drop tables first, if they exist
            sql_statement = '''DROP TABLE IF EXISTS can_list;'''
            execute_sql(conn, sql_statement)

            # Database for ALL the signals from the DBCs for this variant
            sql_statement = '''CREATE TABLE IF NOT EXISTS can_list (
                can_ch integer NOT NULL,
                id integer NOT NULL, 
                name text NOT NULL PRIMARY KEY, 
                byte integer NOT NULL,
                bit integer NOT NULL,
                cycle_ms integer
            );'''
            execute_sql(conn, sql_statement)

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
        print('Waiting for XCP response')
        while received_msg is None or received_msg.arbitration_id != 0x7E1:
            received_msg = bus.recv(0.05)
        # if received_msg.arbitration_id == 0x7E1:
        return received_msg

    def create_message_list(self, dbc_folder):
        """ Create a list of dictionaries of CAN message the following information:
            can_ch - channel of the CAN message
            can_id - ID of the CAN message
            cycle  - transmission cycle of the CAN message in milliseconds

            :return Updates self.message_list
        """
        if self.variant == 'GC7' or self.variant == 'RE7':
            variant_index = 0
        else:
            # HR3
            variant_index = 1
        can_ch = 0
        # DBC list
        #          CAN 1   CAN 2   CAN 3   CAN 4
        # GC7/RE7    *       *       *      *
        # HR3        *       *       *      *
        dbc_list = [
            ['LOCAL1', 'LOCAL2', 'SA', 'PU'],
            ['LOCAL1', 'LOCAL2', 'LOCAL', 'MAIN']
        ]

        logging.info('Creating a list of CAN IDs')
        print('Creating a list of CAN IDs (including DBG signals)')
        for root, dirs, files in os.walk(dbc_folder):
            for file in files:
                if file.endswith(".dbc"):
                    if root.find(self.variant) != -1:
                        if can_ch < 4:
                            if file.find(dbc_list[variant_index][can_ch]) != -1:
                                dbc_file = open(os.path.join(root, file), 'r')
                                for line in dbc_file:
                                    if line.find('BO_ ') != -1 and line.find('EYE') != -1:
                                        data = line.split()
                                        self.message_list.append({'can_ch': can_ch+1, 'can_id': int(data[1]),
                                                                  'cycle_ms': 0})

                                    if line.find('BA_ ') != -1 and line.find('GenMsgCycleTime') != -1:
                                        data = line.split()
                                        for index in range(len(self.message_list)):
                                            if self.message_list[index]['can_ch'] == can_ch+1 and \
                                                    self.message_list[index]['can_id'] == int(data[3]):
                                                if int(data[4][:-1]) == 0:
                                                    self.message_list.remove(self.message_list[index])
                                                else:
                                                    self.message_list[index]['cycle_ms'] = int(data[4][:-1])
                                                break

                                dbc_file.close()
                                can_ch += 1
                            else:
                                pass
                        else:
                            break

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
        # message_status = {}

        print('Checking CAN messages in CAN channel {}'.format(can_ch))

        for index in range(len(self.message_list)):
            if self.message_list[index]['can_ch'] == can_ch:
                can_id = self.message_list[index]['can_id']
                cycle_ms = self.message_list[index]['cycle_ms']
                message_count += 1
                start_s = time.time()
                received_first_s = 0.0
                actual_cycle_ms = 0
                found = False
                while time.time() < start_s + 1.0 and actual_cycle_ms == 0:
                    received_message = bus.recv()
                    if received_message.arbitration_id == can_id:
                        if received_first_s == 0.0:
                            received_first_s = time.time()
                        else:
                            actual_cycle_ms = round((time.time() - received_first_s) * 1000)
                            found = True
                            check_count += 1
                            break

                if not found:
                    hex(12)
                    self.message_status[str(index)] = [can_ch, str(hex(can_id))[2:].upper(), cycle_ms, 'N/A', 'Not Received', 'N/A']
                    logging.info('CAN CH: {} ID {}: Not Received'.format(can_ch, str(hex(can_id))[2:5].upper()))
                else:
                    self.message_status[str(index)] = [can_ch, str(hex(can_id))[2:].upper(), cycle_ms, actual_cycle_ms, 'Received',
                                                       'Failed' if actual_cycle_ms > cycle_ms else 'Passed']
                    logging.info('CAN CH: {} ID {}: Received'.format(can_ch, str(hex(can_id))[2:5].upper()))

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

    def generate_report(self):
        # Dump result to an Excel file
        data_frame = pd.DataFrame.from_dict(self.message_status, orient='index',
                                            columns=['CAN Channel', 'CAN ID', 'Cycle (ms)', 'Actual Cycle (ms)', 'Status', 'Timing']
                                            )
        write_to_excel(data_frame, 'SVS350_{}_CANTx_Checklist.xlsx'.format(self.variant))


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', dest="variant", help='Variant to be checked', choices=['GC7', 'HR3'])
    parser.add_argument('-m', dest="map_folder", help='Path of the MAP file', default='Build/')
    parser.add_argument('-d', dest="dbc_folder", help='Path of the DBC folders for each variant', default='DBC/')
    args = parser.parse_args()

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
    pfptc = PostFlashPreTestCheck(args.variant, args.map_folder, args.dbc_folder)
    # Connect to the XCP slave
    pfptc.connect(pfptc.bus2)
    # pfptc.connect()
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

    logging.shutdown()
    # print('Please check the run.log file')
    print('Generating report')
    pfptc.generate_report()


if len(sys.argv) > 2:
    if __name__ == '__main__':
        main(sys.argv[1:])
else:
    print("Please input arguments: python MergingTextFile.py -v [filename].c -d [filename].xlsx")
