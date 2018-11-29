from pandas import ExcelWriter
from xlrd import open_workbook
from sqlite3 import Error

import sqlite3
import argparse
import os
import pandas as pd

OFF = 0
ON = 1


def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return:
        Connection object or None
    """
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)

    return None


def execute_sql(conn, sql_statement, values=None, select=False):
    """ create a table from the create_table_sql statement
    :param conn: connection object
    :param sql_statement: SQL statement
    :param values: values to INSERT/UPDATE, in case SQL statement is INSERT/UPDATE request
    :param select: SQL statement is a SELECT statement
    :return:
    """
    try:
        c = conn.cursor()
        if values is None:
            c.execute(sql_statement)
            if select:
                return c.fetchall()
        else:
            c.execute(sql_statement, values)
    except Error as e:
        print(e)


def commit_disconnect_database(conn):
    """ Commit the changes done to the SQLite database, then close the connection
    :param conn:
    :return:
    """
    conn.commit()
    conn.close()


def write_to_excel(df, filename, sheet_name):
    writer = ExcelWriter(filename)
    df.to_excel(writer, sheet_name, index=False)
    writer.save()
    writer.close()


def read_excel_file(filename, input_data):
    df = pd.read_excel(filename,
                       sheet_name=input_data[0],
                       usecols=input_data[1],
                       skiprows=input_data[2])
    return df


def parse_arguments_for_input_file():
    # Accepting input
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', dest='input_file', help='Variant: -i [filename]')
    args = parser.parse_args()

    if args.input_file:
        return args.input_file
    else:
        return 0


def get_current_directory(filename):
    base_path = os.path.dirname(os.path.realpath(__file__))
    current_file = os.path.join(base_path, filename)
    
    print(current_file)
