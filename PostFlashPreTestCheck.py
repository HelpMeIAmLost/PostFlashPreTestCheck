#!/usr/bin/env python3
# coding: utf-8

from __future__ import print_function
from time import sleep
from pathlib import Path
from common_util import *
from sqlite3 import Error

import can.interfaces.vector
import logging
import sys
import os
import numpy as np
import sqlite3

logging.basicConfig(filename='run.log', filemode='w', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class PostFlashPreTestCheck(object):
    def __init__(self, variant, map_folder, dbc_folder):
        """ initialize class variables
        :param variant: str
        :param map_folder: str
        :param dbc_folder: str
        """
        self.variant = str(variant).upper()
        self.dbc_folder = Path(dbc_folder)
        self.map_folder = Path(map_folder)
        self.message_list = []
        self.message_status = {}
        self.bus = None

        # # Display CAN output (only 0x7E0 and 0x7E1 messages)
        # self.notifier = can.Notifier(self.bus2, [can.Printer()])

    def get_stub_variable_addresses(self):
        """ search for the addresses of StubVersion_Main and StubVersion_Sub in the Build/application.map file
        """
        addresses = {'StubVersion_Main': 0x0, 'StubVersion_Sub': 0x0}
        key_value = 'StubVersion_Main'
        address_header_found = False
        addresses_found = False

        try:
            with open(self.map_folder / 'application.map', 'r') as fp:
                for line in fp:
                    if line.find('* Symbols (sorted on name)') != -1:
                        address_header_found = True

                    if address_header_found and line.find(key_value) != -1:
                        temp_line = line.split()
                        addresses[key_value] = int(temp_line[3], 16)
                        if key_value == 'StubVersion_Main':
                            key_value = 'StubVersion_Sub'
                        else:
                            addresses_found = True
                            break

                    if line.find('* Symbols (sorted on address)') != -1:
                        break
            fp.close()
        except IOError as e:
            print('I/O error({0}): {1}'.format(e.errno, e.strerror))
            sys.exit()

        return addresses, addresses_found

    def connect(self, xcp_bus):
        try:
            self.bus = can.ThreadSafeBus(bustype='vector', channel=xcp_bus-1,
                                         can_filters=[{"can_id": 0x7e1, "can_mask": 0x7e1, "extended": False}],
                                         receive_own_messages=True, bitrate=500000, app_name='CANoe')
        except can.interfaces.vector.VectorError as message:
            # logging.error(message)
            print(message)
            sys.exit()

        msg = can.Message(arbitration_id=0x7e0,
                          data=[0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                          extended_id=False)
        print('Connecting to XCP slave')
        self.connect_disconnect(msg)

    # Non-short upload commands
    def connect_disconnect(self, msg):
        tries = 0
        self.bus.send(msg)
        response_message = self.check_xcp_response(self.bus)
        # Retry connect/disconnect request 10 times
        while response_message is None and tries < 10:
            if msg.data[0] == 0xFF:
                logging.info("XCP slave connect retry {}".format(tries + 1))
            elif msg.data[0] == 0xFE:
                logging.info("XCP slave disconnect retry {}".format(tries + 1))
            self.bus.send(msg)
            response_message = self.check_xcp_response(self.bus)
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
                    logging.info('Connected to XCP slave through {}'.format(self.bus))
                # DISCONNECT
                else:
                    logging.info('Disconnected from XCP slave')
            # PID: ERR
            elif response_message.data[0] == 0xFE:
                # response indicates error, report error
                if msg.data[0] == 0xFF:
                    logging.error('Unable to connect to XCP slave through {}'.format(self.bus))
                else:
                    logging.error('Unable to disconnect from XCP slave through {}'.format(self.bus))
                sys.exit()
            # Error: XCP_ERR_CMD_UNKNOWN
            elif response_message.data[0] == 0x20:
                logging.info('Command: {} Response: XCP_ERR_CMD_UNKNOWN'.format(command))
                sys.exit()
            else:
                logging.info('Command: {} Response: {}'.format(command,
                                                               hex(response_message.data[0])))
                sys.exit()

    def get_stub_version(self, msg1, msg2):
        tries = 0

        logging.info('Checking for the stub version..')
        print('Checking for the stub version..')

        response_message = None

        while response_message is None and tries < 10:
            # StubVersion_Main
            self.bus.send(msg1)
            response_message = self.check_xcp_response(self.bus)
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
                self.bus.send(msg2)
                tries = 0
                response_message = None
                while response_message is None and tries < 10:
                    # StubVersion_Main
                    self.bus.send(msg2)
                    response_message = self.check_xcp_response(self.bus)
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

    def disconnect(self):
        # self.notifier.stop()
        msg = can.Message(arbitration_id=0x7e0,
                          data=[0xFE, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                          extended_id=False)
        print('Disconnecting from XCP slave')
        self.connect_disconnect(msg)
        self.bus.shutdown()

    @staticmethod
    def check_xcp_response(bus):
        # Set timeout for response message
        received_msg = bus.recv(0.05)
        print('Waiting for XCP response')
        while received_msg is None or received_msg.arbitration_id != 0x7E1:
            received_msg = bus.recv(0.05)
        # if received_msg.arbitration_id == 0x7E1:
        return received_msg

    def create_message_list(self):
        """ Creates a dictionary of CAN message information

            :param dbc_folder: The location of the DBC files relative to the script folder, with 1 folder per variant
            :return: Updated class variable message_list
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
        for root, dirs, files in os.walk(self.dbc_folder):
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

        :param can_ch: CAN channel to check for CAN messages
        :return: Result of CAN message-checking for the current CAN channel
        """
        bus = can.interface.Bus(bustype='vector', channel=can_ch-1,
                                receive_own_messages=False, bitrate=500000, app_name='CANoe')

        # CAN logger
        asc_file = 'CAN'+str(can_ch)+'_log.asc'
        can_log = open(asc_file, 'w+')
        asc_writer = can.ASCWriter(asc_file)
        notifier = can.Notifier(bus, [asc_writer])
        sleep(5)
        can_log.close()
        # logging.shutdown()
        notifier.stop()
        asc_writer.stop()
        bus.shutdown()

        message_count = 0
        check_count = 0
        # message_status = {}

        print('Checking CAN messages in CAN channel {}'.format(can_ch))
        for index in range(len(self.message_list)):
            if self.message_list[index]['can_ch'] == can_ch:
                can_id = self.message_list[index]['can_id']
                cycle_ms = self.message_list[index]['cycle_ms']
                message_count += 1
                message_found = False
                message_tx_num = 0
                time_0_s = 0.0
                time_diff_ms = 0
                with open(asc_file, 'r') as fp:
                    for line in fp:
                        if line.find('  {}             Rx'.format(str(hex(can_id)[2:]).upper())) != -1:
                            if not message_found:
                                message_found = True
                                check_count += 1
                            message_tx_num += 1
                            if message_tx_num > 4:
                                message_rx = line.split()
                                if time_0_s == 0.0:
                                    time_0_s = float(message_rx[0])
                                else:
                                    time_diff_ms += (float(message_rx[0]) - time_0_s) * 1000
                                    time_0_s = float(message_rx[0])

                fp.close()
                if message_found:
                    time_diff_ms = round(time_diff_ms / (message_tx_num - 4))
                    self.message_status[str(index)] = [can_ch, str(hex(can_id))[2:].upper(), cycle_ms, time_diff_ms,
                                                       'Received', 'Failed' if time_diff_ms > cycle_ms else 'Passed',
                                                       'Please refer to CAN{}_log.asc'.format(can_ch)
                                                       if time_diff_ms > cycle_ms else np.nan]
                    logging.info('CAN CH: {} ID {}: Received'.format(can_ch, str(hex(can_id))[2:5].upper()))
                else:
                    self.message_status[str(index)] = [can_ch, str(hex(can_id))[2:].upper(), cycle_ms, 'N/A',
                                                       'Not Received', 'N/A']
                    logging.info('CAN CH: {} ID {}: Not Received'.format(can_ch, str(hex(can_id))[2:5].upper()))

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
        """ Generates a simple report of the CAN message checking in Excel format

        :return: None
        """
        # Dump result to an Excel file
        data_frame = pd.DataFrame.from_dict(self.message_status, orient='index',
                                            columns=['CAN Channel', 'CAN ID', 'Cycle (ms)', 'Average Cycle (ms)',
                                                     'Status', 'Timing', 'Notes']
                                            )
        write_to_excel(data_frame, 'SVS350_{}_CANTx_Checklist.xlsx'.format(self.variant), self.variant)

    def update_internal_signals(self):
        conn = create_connection('interface.db')
        if conn is not None:
            sql_select = '''SELECT link FROM internal_signals;'''
            sql_update_internal_signal = ''' UPDATE internal_signals
                      SET address = ?
                      WHERE link = ?;'''
            rows = execute_sql(conn, sql_select, select=True)
            for row in rows:
                address_header_found = False
                with open(self.map_folder / 'application.map', 'r') as fp:
                    for line in fp:
                        if line.find('* Symbols (sorted on name)') != -1:
                            address_header_found = True

                        if address_header_found and line.find(row) != -1:
                            internal_signal_name = row
                            temp_line = line.split()
                            internal_signal_address = int(temp_line[3], 16)
                            execute_sql(conn, sql_update_internal_signal,
                                        (internal_signal_name, internal_signal_address))
                            break
        else:
            print("Error! cannot create the database connection.")


parser = argparse.ArgumentParser()
parser.add_argument("variant", help='variant to be checked', choices=['GC7', 'HR3'])
parser.add_argument('-m', dest="map_folder", help='path of the MAP file', default='Build/')
parser.add_argument('-d', dest="dbc_folder", help='path of the DBC folders for each variant', default='DBC/')
args = parser.parse_args()

pretest_check = PostFlashPreTestCheck(args.variant, args.map_folder, args.dbc_folder)
# pretest_check = PostFlashPreTestCheck('GC7', 'Build/', 'DBC/')
# Update with address of StubVersion_Main
signal_address, found = pretest_check.get_stub_variable_addresses()
if found:
    message1 = can.Message(arbitration_id=0x7E0,
                           data=[0xF4, 1, 0x0, 0x0,
                                 signal_address['StubVersion_Main'] & 0xFF,
                                 (signal_address['StubVersion_Main'] >> 8) & 0xFF,
                                 (signal_address['StubVersion_Main'] >> 16) & 0xFF,
                                 (signal_address['StubVersion_Main'] >> 24) & 0xFF],
                           extended_id=False)
    message2 = can.Message(arbitration_id=0x7E0,
                           data=[0xF4, 1, 0x0, 0x0,
                                 signal_address['StubVersion_Sub'] & 0xFF,
                                 (signal_address['StubVersion_Sub'] >> 8) & 0xFF,
                                 (signal_address['StubVersion_Sub'] >> 16) & 0xFF,
                                 (signal_address['StubVersion_Sub'] >> 24) & 0xFF],
                           extended_id=False)
    print('Starting post-flash checking..')
    # Connect to the XCP slave
    pretest_check.connect(2)
    # pretest_check.connect()
    # Poll the output signal every 10ms
    pretest_check.get_stub_version(message1, message2)
    sleep(1)
    # Disconnect from XCP slave
    pretest_check.disconnect()
else:
    print('Cannot determine stub version. Please make sure the latest version of the application stub modules is used.')

print('Creating a list of CAN IDs (including DBG signals)')
pretest_check.create_message_list()
print('Waiting for CAN messages..')
pretest_check.wait_for_messages(1)
pretest_check.wait_for_messages(2)
pretest_check.wait_for_messages(3)
pretest_check.wait_for_messages(4)
logging.shutdown()
# print('Please check the run.log file')
print('Generating report')
pretest_check.generate_report()
print('Done!')

# Update the interface database for interface test
# Update internal signal information
pretest_check.update_internal_signals()
# Update external signal information