import sqlite3
from configparser import ConfigParser
import logging

""" 
In order to instantiate the SQLiteHelper class, you need an ini file denoting the table name and structure. 

Example: 
[TABLENAMEHERE]
*name=TEXT # * denotes the field as part of the primary key of the DB
age=TEXT
height=REAL

"""


def load_config(filename, section):
    parser = ConfigParser()
    parser.read(filename)
    config = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            config[param[0]] = param[1]
    else:
        raise Exception(f'Section {section} not found in the {filename} file')
    return config


def parse_table_config(input_config):
    return_list = []
    for key, value in input_config.items():
        return_list.append((f'{key.replace("*", "")} {value}', key[0] == '*'))
    return return_list


class SQLiteHelper:

    def __init__(self, db_file, db_name):
        self.__config = load_config(db_file, db_name)
        self.__config_list = parse_table_config(self.__config)
        self.__establish_db_conn(db_name)
        self.db_name = db_name
        self.__create_table()

    def __create_table(self):
        """Create SQLite db if it doesn't exist. """

        table_name = self.db_name
        table_layout = self.__config_list

        __command_string__ = f"""CREATE TABLE IF NOT EXISTS {table_name} ("""
        primary_key_fields = []


        for line in table_layout:
            __command_string__ += f'{line[0]}, '
            if line[1]:  
                primary_key_fields.append(line[0].split(' ')[0])

        if primary_key_fields:  
            __command_string__ += f'PRIMARY KEY ({", ".join(primary_key_fields)})'
        else:
            __command_string__ = __command_string__.rstrip(', ')

        __command_string__ += ')'  

        try:
            self.cursor.execute(__command_string__)
            self.conn.commit()
        except sqlite3.OperationalError as se:
            logging.error(f'Exception Occurred: {se}')

    def __establish_db_conn(self, db_name):
        """Handle creating the SQLite file/open the existing one."""

        self.conn = sqlite3.connect(f'{db_name}.db')
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def execute_query(self, query, params=None):
        """Function for handling executing SQL queries. params will be None in almost all cases, added for some things
        planned for the future. """
        try:
            if params is not None:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            self.conn.commit()
            result = self.cursor.fetchall()
            return [dict(row) for row in result]

        except Exception as e:
            self.conn.rollback()
            logging.error(f'Exception occurred, rolled back any changes. Error: {e}')
            return []

    def select_data(self, selection_items, selection_where=None):
        """Select command for retrieving information from the database. selection_items is the column name.
        selection_where is the optional where clause. Example: selection_where age > 10 will filter results to rows
        where age is greater than 10
        """

        query = f'SELECT {selection_items} FROM {self.db_name}'
        if selection_where:
            query += f' WHERE {selection_where}'
        try:
            data = self.execute_query(query)
            self.conn.commit()
            logging.info(data)
            if data:
                return data
            else:
                return f'No data returned.'

        except Exception as e:
            self.conn.rollback()
            logging.error(f'Select failed, rolled back. Error: {e}')
            return f'Select failed, rolled back. Error: {e}'

    def insert_data(self, query_columns, query_values):
        """Insert data into SQLite Database.
        query_columns takes a tuple of the columns in the table where you want to insert data.
        query_values takes a tuple of the values you would like to insert into the db."""

        columns = ', '.join(query_columns)

        formatted_values = []
        for value in query_values:
            if isinstance(value, str):
                formatted_values.append(f"'{value}'")
            elif value is None:
                formatted_values.append('NULL')
            else:
                formatted_values.append(str(value))

        values = ', '.join(formatted_values)
        query = f'INSERT INTO {self.db_name} ({columns}) VALUES ({values})'
        try:
            self.cursor.execute(query)
            self.conn.commit()
            logging.info("Data inserted successfully.")
            return "Data inserted successfully."

        except Exception as e:
            self.conn.rollback()
            logging.error(f'Insertion failed, rolled back. Error: {e}')
            return f'Insertion failed, rolled back. Error: {e}'

    def delete_data(self, column_name, value_to_delete):
        """Used for deleting data from the table associated with the SQLite file."""

        query = f"DELETE FROM {self.db_name} WHERE {column_name} = ?"
        try:
            self.execute_query(query, (value_to_delete,))
            self.conn.commit()
            logging.info("Data deleted successfully.")
            return "Data deleted successfully"
        except Exception as e:
            self.conn.rollback()
            logging.error(f'Deletion failed, rolled back. Error: {e}')
            return f'Deletion failed, rolled back. Error: {e}'

    def update_data(self, update_data_dictionaries, where_clause):
        """Update SQLite DB data. Takes a list of dictionaries.
        key of the dictionary is the column that is being updated,
        value is the value to update.
        where_clause takes logic for the WHERE statement. Example: "age=0" for updating column values where age=0 """

        merged_dict = {}
        for dictionary in update_data_dictionaries:
            merged_dict.update(dictionary)

        set_parts = []
        for key, value in merged_dict.items():
            if isinstance(value, str):
                set_parts.append(f"{key}='{value}'")
            elif value is None:
                set_parts.append(f"{key}=NULL")
            else:
                set_parts.append(f"{key}={value}")

        set_clause = ', '.join(set_parts)

        query = f"UPDATE {self.db_name} SET {set_clause} WHERE {where_clause}"
        try:
            self.execute_query(query)
            self.conn.commit()
            logging.info("Data updated successfully.")
            return "Data updated successfully."

        except Exception as e:
            self.conn.rollback()
            logging.error(f'Update failed, rolled back. Error: {e}')
            return f'Update failed, rolled back. Error: {e}'

    def select_min(self, column_name):
        """Specialized Select command for retrieving information from the database. column_name is the column name.
        This will return the minimum value of the rows based on the column name.
         """
        query = f"SELECT MIN({column_name}) FROM {self.db_name}"

        try:
            data = self.execute_query(query)
            self.conn.commit()
            logging.info(f"Minimum from {column_name}: {data}.")
            return f"Minimum from {column_name}: {data}."

        except Exception as e:
            self.conn.rollback()
            logging.error(f'Selection failed, rolled back. Error: {e}')
            return f'Selection failed, rolled back. Error: {e}'

    def select_max(self, column_name):
        """Specialized Select command for retrieving information from the database. column_name is the column name.
        This will return the maximum value of the rows based on the column name.
         """

        query = f"SELECT MAX({column_name}) FROM {self.db_name}"
        try:
            data = self.execute_query(query)
            self.conn.commit()
            logging.info(f"Maximum from {column_name}: {data}.")
            return f"Maximum from {column_name}: {data}."

        except Exception as e:
            self.conn.rollback()
            logging.error(f'Selection failed, rolled back. Error: {e}')
            return f'Selection failed, rolled back. Error: {e}'

    def select_avg(self, column_name):
        """Specialized Select command for retrieving information from the database. column_name is the column name.\
        This will return the average value of the rows based on the column name.
         """

        query = f"SELECT AVG({column_name}) FROM {self.db_name}"
        try:
            data = self.execute_query(query)
            self.conn.commit()
            logging.info(f"Average from {column_name}: {data}.")
            return f"Average from {column_name}: {data}."

        except Exception as e:
            self.conn.rollback()
            logging.error(f'Selection failed, rolled back. Error: {e}')
            return f'Selection failed, rolled back. Error: {e}'

if __name__ == "__main__":
    ...
    # Example instantiation of the SQLiteHelper class. Creates DB files/table if they don't exist
    # table = SQLiteHelper('tableconfig.ini', 'testtable')

    # Example of data insertion
    # table.insert_data(query_columns=('name', 'age'), query_values=('tester', 3))

    # Example of data deletion
    # table.delete_data('age', '3')

    # Example of updating data
    # table.update_data([{'name':'testing'}], 'age=2')

    # Example of selection data
    # table.select_data('name, age')
