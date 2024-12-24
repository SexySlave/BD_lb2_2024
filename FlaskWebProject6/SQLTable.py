import mysql.connector
import pandas as pd
import os
import datetime
import json
# import keyword_handling as kwd
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)


class SQLTable:
    def __init__(self, db_config, table_name):
        """
        Initialize with database configuration and table name.

        :param db_config: Dictionary with keys 'user', 'password', 'host', 'database'.
        :param table_name: Name of the table in the database.
        """
        self.db_config = db_config
        self.table_name = table_name
        self.connection = mysql.connector.connect(**db_config)
        self.cursor = self.connection.cursor()
        self.columns = []

        # Check if the table exists and update column names
        if not self._check_table_exists():
            print(f"Error: Table '{self.table_name}' does not exist. Please use create_table method to create it.")
        else:
            self._update_column_names()

    def _check_table_exists(self):
        """
        Check if the table exists in the database.
        """
        query = f"SHOW TABLES LIKE '{self.table_name}'"
        self.cursor.execute(query)
        return self.cursor.fetchone() is not None

    def _update_column_names(self):
        """
        Updates the list of column names from the database table.
        """
        query = f"SHOW COLUMNS FROM {self.table_name}"
        self.cursor.execute(query)
        self.columns = [row[0] for row in self.cursor.fetchall()]

    def create_table(self, columns):
        """
        Creates a new table if it does not exist with the specified columns and an auto-incrementing primary key 'id'.

        :param columns: A dictionary where keys are column names and values are SQL data types.
        """
        column_definition = ', '.join(f"`{name}` {type}" for name, type in columns.items())
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            {column_definition}
        )
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()
        self._update_column_names()
        print(f"Table '{self.table_name}' created with columns {self.columns}.")

    def fetch_one(self, column_name, value):
        """
        Fetches a single row from the table where column_name equals the provided value.

        Parameters:
            column_name (str): The name of the column to filter on.
            value: The value to match in the specified column.

        Returns:
            dict: A dictionary representing the single row fetched, or None if no row matches.
        """
        cursor = self.connection.cursor()
        try:
            query = f"SELECT * FROM {self.table_name} WHERE {column_name} = %s"
            cursor.execute(query, (value,))
            row = cursor.fetchone()
            if row:
                column_names = [col[0] for col in cursor.description]
                return dict(zip(column_names, row))
            else:
                return None
        finally:
            cursor.close()

    def fetch_all(self):
        """
        Fetches all rows from the table and returns them as a DataFrame.
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM {self.table_name}")
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def fetch_all_ordered(self, order_column, ascending=True):
        """
        Fetches all rows from the table ordered by a specified column.
        """
        order_direction = "ASC" if ascending else "DESC"
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM {self.table_name} ORDER BY `{order_column}` {order_direction}")
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def fetch_column(self, column_name):
        """
        Fetches the primary key column and one additional specified column from the table.

        :param column_name: Name of the additional column to fetch.
        :return: DataFrame containing the primary key column and the requested additional column.
        """
        # First, identify the primary key column
        primary_key = self._find_primary_key()
        if not primary_key:
            print("No primary key found for the table.")
            return pd.DataFrame()  # Return empty DataFrame if no primary key is found

        # Construct the SQL query to select the primary key and specified column
        query = f"SELECT `{primary_key}`, `{column_name}` FROM {self.table_name}"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            # Create a DataFrame from the fetched rows
            df = pd.DataFrame(rows, columns=[primary_key, column_name])
        finally:
            cursor.close()  # Ensure the cursor is closed after operation

        return df

    def _find_primary_key(self):
        """
        Determines the primary key column of the current table.
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SHOW KEYS FROM {self.table_name} WHERE Key_name = 'PRIMARY'")
            result = cursor.fetchone()
            if result:
                return result[4]  # Column name is in the fifth position in the result set
        finally:
            cursor.close()
        return None

    def insert_row(self, data):
        """
        Inserts a new row into the table.

        :param data: Dictionary where keys are column names and values are the data for those columns.
        """
        columns = ', '.join(f"`{k}`" for k in data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        values = tuple(data.values())

        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, values)
            self.connection.commit()
        finally:
            cursor.close()

    def delete_row_by_id(self, id):
        """
        Deletes a row from the table based on its primary key ID.

        :param id: ID of the row to be deleted.
        """
        # Determine the primary key column name
        primary_key = self._find_primary_key()
        if not primary_key:
            print("No primary key found for the table.")
            return False  # Indicate failure if no primary key is found

        # Prepare the SQL query using the primary key
        query = f"DELETE FROM {self.table_name} WHERE `{primary_key}` = %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (id,))
            self.connection.commit()
            return True  # Indicate success
        finally:
            cursor.close()

    def delete_rows_by_ids(self, ids):
        """
        Deletes multiple rows from the table based on a list of IDs.

        :param ids: List of IDs for the rows to be deleted.
        """
        for id in ids:
            self.delete_row_by_id(id)

    def select_rows_by_ids(self, ids):
        """
        Selects multiple rows from the table based on a list of IDs.

        :param ids: List of IDs for the rows to select.
        :return: DataFrame containing the selected rows.
        """
        primary_key = self._find_primary_key()
        if not primary_key:
            print("Primary key not found.")
            return pd.DataFrame()  # Return empty DataFrame if no primary key is found

        ids_tuple = tuple(ids)  # Ensure ids are in a tuple for the SQL IN clause
        query = f"SELECT * FROM {self.table_name} WHERE `{primary_key}` IN {ids_tuple}"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [i[0] for i in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def select_row_by_id(self, id):
        """
        Selects a row from the table based on its primary key ID.

        :param id: ID of the row to select.
        :return: DataFrame containing the selected row.
        """
        primary_key = self._find_primary_key()
        if not primary_key:
            print("Primary key not found.")
            return pd.DataFrame()  # Return empty DataFrame if no primary key is found

        query = f"SELECT * FROM {self.table_name} WHERE `{primary_key}` = %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (id,))
            row = cursor.fetchall()
            column_names = [i[0] for i in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(row, columns=column_names)

    def update_column_by_id(self, id, column_name, new_value):
        """
        Updates a specific column of a specific row identified by the primary key.

        :param id: ID of the row to update.
        :param column_name: Name of the column to update.
        :param new_value: New value to set for the column.
        """
        primary_key = self._find_primary_key()  # Fetch the primary key column name
        if not primary_key:
            print("Primary key not found.")
            return False  # Exit the function if no primary key is found

        query = f"UPDATE {self.table_name} SET `{column_name}` = %s WHERE `{primary_key}` = %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (new_value, id))
            self.connection.commit()
            return True  # Indicate successful update
        except Exception as e:
            print(f"Failed to update row: {e}")
            return False  # Indicate unsuccessful update
        finally:
            cursor.close()

    def rename_table(self, new_table_name):
        """
        Renames the current table and updates the class's table_name attribute.

        :param new_table_name: The new name for the table.
        """
        query = f"ALTER TABLE {self.table_name} RENAME TO {new_table_name}"
        self.cursor.execute(query)
        self.connection.commit()
        self.table_name = new_table_name  # Update the instance variable to the new table name

    def export_to_csv(self):
        """
        Exports the entire table to a CSV file located in the user's Downloads folder.
        """
        """
            Exports the entire table to a CSV file located in the user's Downloads folder.
            Includes a timestamp in the filename to prevent overwriting and to track export times.
            """
        # Fetch all data from the table
        df = self.fetch_all()

        # Define the path to the Downloads folder
        downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')

        # Check if the Downloads directory exists, if not, create it
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path)

        # Get current timestamp
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        # Construct the filename with a timestamp
        file_name = f"{self.table_name}_{timestamp}.csv"
        file_path = os.path.join(downloads_path, file_name)

        # Write the DataFrame to a CSV file
        df.to_csv(file_path, index=False)
        print(f"Data exported successfully to {file_path}")

    def select_rows_by_id_range(self, start_id, end_id):
        """
        Selects all rows between start_id and end_id (inclusive), based on the primary key.

        :param start_id: The starting ID of the range.
        :param end_id: The ending ID of the range.
        :return: DataFrame containing the selected rows.
        """
        primary_key = self._find_primary_key()  # Fetch the primary key column name
        if not primary_key:
            print("Primary key not found.")
            return pd.DataFrame()  # Return empty DataFrame if no primary key is found

        query = f"SELECT * FROM {self.table_name} WHERE `{primary_key}` BETWEEN %s AND %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (start_id, end_id))
            rows = cursor.fetchall()
            column_names = [i[0] for i in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def select_rows_by_column_value(self, column_name, value):
        """
        Selects rows where the column value equals a given value.

        :param column_name: The name of the column to check.
        :param value: The value to match in the specified column.
        :return: DataFrame containing the selected rows.
        """
        query = f"SELECT * FROM {self.table_name} WHERE `{column_name}` = %s"
        self.cursor.execute(query, (value,))
        rows = self.cursor.fetchall()
        column_names = [i[0] for i in self.cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        return df

    def delete_rows_by_id_range(self, start_id, end_id):
        """
        Deletes all rows between start_id and end_id (inclusive), based on the primary key.

        :param start_id: The starting ID of the range.
        :param end_id: The ending ID of the range.
        """
        primary_key = self._find_primary_key()  # Fetch the primary key column name
        if not primary_key:
            print("Primary key not found.")
            return  # Exit the function if no primary key is found

        query = f"DELETE FROM {self.table_name} WHERE `{primary_key}` BETWEEN %s AND %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (start_id, end_id))
            self.connection.commit()
            print(f"Deleted rows from {primary_key} {start_id} to {end_id}.")
        finally:
            cursor.close()

    def delete_rows_by_column_value(self, column_name, value):
        """
        Deletes rows where the column value equals a given value.

        :param column_name: The name of the column to check.
        :param value: The value to match in the specified column.
        """
        query = f"DELETE FROM {self.table_name} WHERE `{column_name}` = %s"
        self.cursor.execute(query, (value,))
        self.connection.commit()
        print(f"Deleted rows where {column_name} = {value}.")

    def drop_table(self):
        """
        Drops the table corresponding to self.table_name if it exists.
        """
        cursor = self.connection.cursor()
        try:
            query = f"DROP TABLE IF EXISTS {self.table_name}"
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Table '{self.table_name}' has been dropped.")

    def add_column(self, column_name, data_type):
        """
        Adds a new column to the existing table.

        :param column_name: The name of the column to be added.
        :param data_type: The SQL data type for the new column.
        """
        query = f"ALTER TABLE {self.table_name} ADD COLUMN `{column_name}` {data_type}"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Column '{column_name}' of type '{data_type}' added to table '{self.table_name}'.")

    def delete_column(self, column_name):
        """
        Deletes a column from the existing table.
        """
        cursor = self.connection.cursor()
        try:
            query = f"ALTER TABLE {self.table_name} DROP COLUMN `{column_name}`"
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()

    def count_rows(self):
        """
        Returns the number of rows in the table.
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            result = cursor.fetchone()
            count = result[0] if result else 0
        finally:
            cursor.close()
        print(f"Total rows in '{self.table_name}': {count}")
        return count

    def search_column_for_string(self, column_name, search_string):
        """
        Searches for a string within a specified column and returns a DataFrame with the results.
        Also prints the number of results found. Validates that the column exists before searching.

        :param column_name: The name of the column to search in.
        :param search_string: The string to search for within the column.
        :return: A DataFrame containing the rows where the search string was found in the specified column.
        """
        # Validate that the column name exists in the table
        if column_name not in self.columns:
            print(f"Error: Column '{column_name}' does not exist in the table '{self.table_name}'.")
            return pd.DataFrame()  # Return an empty DataFrame if the column does not exist

        query = f"SELECT * FROM {self.table_name} WHERE `{column_name}` LIKE %s"
        search_pattern = f"%{search_string}%"  # Use '%' wildcards for partial matching
        self.cursor.execute(query, (search_pattern,))
        rows = self.cursor.fetchall()
        column_names = [col[0] for col in self.cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        print(f"Found {len(df)} results for search string '{search_string}' in column '{column_name}'.")
        return df

    def search_column_for_int(self, column_name, search_int):
        """
        Searches for an integer within a specified column and returns a DataFrame with the results.
        Also prints the number of results found. Validates that the column exists before searching.

        :param column_name: The name of the column to search in.
        :param search_int: The integer to search for within the column.
        :return: A DataFrame containing the rows where the search integer was found in the specified column.
        """
        # Validate that the column name exists in the table
        if column_name not in self.columns:
            print(f"Error: Column '{column_name}' does not exist in the table '{self.table_name}'.")
            return pd.DataFrame()  # Return an empty DataFrame if the column does not exist

        query = f"SELECT * FROM {self.table_name} WHERE `{column_name}` = %s"
        self.cursor.execute(query, (search_int,))
        rows = self.cursor.fetchall()
        column_names = [col[0] for col in self.cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        print(f"Found {len(df)} results for search integer '{search_int}' in column '{column_name}'.")
        return df

    def inner_join(self, other_table, join_column, other_join_column=None, select_columns='*', where_clause=''):
        """
        Performs an inner join between the current table and another table.

        :param other_table: The name of the other table to join with.
        :param join_column: The column name in the current table to join on.
        :param other_join_column: The column name in the other table to join on. If None, assumes same as join_column.
        :param select_columns: A string of columns to select, defaults to '*' for all columns.
        :param where_clause: Additional SQL conditions for the join, defaults to an empty string.
        :return: A DataFrame containing the result of the join.
        """
        # Use the same join column for both tables if other_join_column is not provided
        if not other_join_column:
            other_join_column = join_column

        # Construct the SQL query
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name}
        INNER JOIN {other_table} ON {self.table_name}.`{join_column}` = {other_table}.`{other_join_column}`
        {where_clause}
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()

        return pd.DataFrame(rows, columns=column_names)

    def import_from_csv(self, file_path, columns=None):
        """
        Imports data from a CSV file into the database table.

        :param file_path: Path to the CSV file.
        :param columns: List of columns to import; if None, assumes the first row of the CSV contains headers.
        """
        # Read the CSV file
        df = pd.read_csv(file_path, header=0 if columns is None else None)
        if columns is not None:
            df.columns = columns

        # Insert data into the table
        self._bulk_insert_dataframe(df)

    def import_from_excel(self, file_path, columns=None):
        """
        Imports data from an Excel file into the database table.

        :param file_path: Path to the Excel file.
        :param columns: List of columns to import; if None, assumes the first row of the Excel contains headers.
        """
        # Read the Excel file
        df = pd.read_excel(file_path, header=0 if columns is None else None)
        if columns is not None:
            df.columns = columns

        # Insert data into the table
        self._bulk_insert_dataframe(df)

    def _bulk_insert_dataframe(self, df):
        """
        Helper method to insert data from a DataFrame into the database table.
        """
        placeholders = ', '.join(['%s'] * len(df.columns))
        columns = ', '.join([f"`{column}`" for column in df.columns])
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        data = df.to_records(index=False)

        cursor = self.connection.cursor()
        try:
            # Insert data in batches
            for record in data:
                cursor.execute(query, tuple(record))
            self.connection.commit()
        finally:
            cursor.close()

    def left_join(self, other_table, join_column, other_join_column=None, select_columns='*', where_clause=''):
        """
        Performs a left join between the current table and another table.

        :param other_table: Name of the other table to join with.
        :param join_column: Column name in the current table to join on.
        :param other_join_column: Column name in the other table to join on, if different from join_column.
        :param select_columns: Columns to select, defaults to '*' for all columns.
        :param where_clause: Additional SQL conditions for the join.
        :return: DataFrame containing the result of the join.
        """
        other_join_column = other_join_column or join_column
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name}
        LEFT JOIN {other_table} ON {self.table_name}.`{join_column}` = {other_table}.`{other_join_column}`
        {where_clause}
        """
        return self._execute_query(query)

    def right_join(self, other_table, join_column, other_join_column=None, select_columns='*', where_clause=''):
        """
        Performs a right join between the current table and another table.

        :param other_table: Name of the other table to join with.
        :param join_column: Column name in the current table to join on.
        :param other_join_column: Column name in the other table to join on, if different from join_column.
        :param select_columns: Columns to select, defaults to '*' for all columns.
        :param where_clause: Additional SQL conditions for the join.
        :return: DataFrame containing the result of the join.
        """
        other_join_column = other_join_column or join_column
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name}
        RIGHT JOIN {other_table} ON {self.table_name}.`{join_column}` = {other_table}.`{other_join_column}`
        {where_clause}
        """
        return self._execute_query(query)

    def cross_join(self, other_table, select_columns='*'):
        """
        Performs a cross join between the current table and another table.

        :param other_table: Name of the other table to join with.
        :param select_columns: Columns to select, defaults to '*' for all columns.
        :return: DataFrame containing the result of the join.
        """
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name}
        CROSS JOIN {other_table}
        """
        return self._execute_query(query)

    def self_join(self, join_column, alias_one='a', alias_two='b', select_columns='*', where_clause=''):
        """
        Performs a self join on the current table.

        :param join_column: Column name to join on.
        :param alias_one: Alias for the first instance of the table.
        :param alias_two: Alias for the second instance of the table.
        :param select_columns: Columns to select, defaults to '*' for all columns.
        :param where_clause: Additional SQL conditions for the join.
        :return: DataFrame containing the result of the join.
        """
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name} AS {alias_one}
        JOIN {self.table_name} AS {alias_two} ON {alias_one}.`{join_column}` = {alias_two}.`{join_column}`
        {where_clause}
        """
        return self._execute_query(query)

    def _execute_query(self, query):
        """
        Executes a given SQL query and returns the results as a DataFrame.
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def update_range(self, id_start, id_end, column_name, new_value):
        """
        Updates a specified column to a new value for all records within a given range of IDs.

        :param id_start: The starting ID for the range.
        :param id_end: The ending ID for the range.
        :param column_name: The column to update.
        :param new_value: The new value to set, can be various data types.
        """
        cursor = self.connection.cursor()
        try:
            # Prepare the query and handle different data types appropriately
            query = f"UPDATE {self.table_name} SET `{column_name}` = %s WHERE `id` BETWEEN %s AND %s"
            cursor.execute(query, (new_value, id_start, id_end))
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Updated records from ID {id_start} to {id_end} setting `{column_name}` to {new_value}.")

    def update_where(self, column_name, new_value, where_clause):
        """
        Updates a specified column to a new value based on a custom WHERE clause.

        :param column_name: The column to update.
        :param new_value: The new value to set, can be various data types.
        :param where_clause: The WHERE clause specifying which records to update.
        """
        cursor = self.connection.cursor()
        try:
            # Construct the full SQL update statement including the WHERE clause
            query = f"UPDATE {self.table_name} SET `{column_name}` = %s {where_clause}"
            cursor.execute(query, (new_value,))
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Updated `{column_name}` to {new_value} where {where_clause}.")

    def select_where(self, where_clause, select_columns='*'):
        """
        Selects rows based on a custom WHERE clause.

        :param where_clause: The WHERE clause specifying which records to select.
        :param select_columns: The columns to select, defaults to '*' for all columns.
        :return: A DataFrame containing the selected rows.
        """
        cursor = self.connection.cursor()
        try:
            query = f"SELECT {select_columns} FROM {self.table_name} {where_clause}"
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def delete_where(self, where_clause):
        """
        Deletes rows based on a custom WHERE clause.

        :param where_clause: The WHERE clause specifying which records to delete.
        """
        cursor = self.connection.cursor()
        try:
            query = f"DELETE FROM {self.table_name} {where_clause}"
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Deleted rows {where_clause}.")

    def recreate_table(self):
        """
        Recreates the current table with the same data structure but without any data.
        This involves capturing the table's schema, dropping the table, and then recreating it.
        """
        # First, fetch the create table statement for the existing table
        create_statement = self._fetch_create_statement()
        if not create_statement:
            print(f"Failed to fetch CREATE statement for the table '{self.table_name}'.")
            return

        # Drop the current table
        self.drop_table()

        # Recreate the table using the fetched create statement
        cursor = self.connection.cursor()
        try:
            cursor.execute(create_statement)
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Table '{self.table_name}' was recreated successfully.")

    def _fetch_create_statement(self):
        """
        Fetches the CREATE TABLE statement for the current table to replicate its schema.
        """
        cursor = self.connection.cursor()
        try:
            # This SQL query varies by database; example here is for MySQL.
            cursor.execute(f"SHOW CREATE TABLE {self.table_name}")
            result = cursor.fetchone()
            create_statement = result[1] if result else None
        finally:
            cursor.close()
        return create_statement

    def export_table_to_sql(self):
        """
        Exports the current table's schema and all its data to a SQL file in the Downloads folder.
        """
        create_statement = self._fetch_create_statement()
        if not create_statement:
            print(f"Failed to fetch CREATE statement for the table '{self.table_name}'.")
            return

        data = self.fetch_all()
        insert_statements = self._generate_insert_statements(data)

        # Combine create statement and insert statements
        sql_commands = f"{create_statement};\n\n{insert_statements}"

        # Filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"{self.table_name}_{timestamp}.sql"
        downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path)
        file_path = os.path.join(downloads_path, filename)

        # Write to file
        with open(file_path, 'w') as file:
            file.write(sql_commands)
        print(f"Table '{self.table_name}' exported to SQL file: {file_path}")

    def _generate_insert_statements(self, data):
        """
        Generates INSERT SQL statements for a DataFrame.
        """
        inserts = []
        for _, row in data.iterrows():
            columns = ', '.join([f"`{col}`" for col in data.columns])
            values = ', '.join(
                [f"'{SQLTable.escape_sql_string(val)}'" if isinstance(val, str) else str(val) for val in row])
            inserts.append(f"INSERT INTO `{self.table_name}` ({columns}) VALUES ({values});")
        return '\n'.join(inserts)

    @staticmethod
    def escape_sql_string(value):
        """Escape single quotes in SQL string literals by replacing them with double single quotes."""
        trans_table = {ord(','): None, ord(':'): None, ord('.'): None, ord('&'): None, ord('!'): None, ord('"'): None,
                       ord('?'): None, ord('\n'): None, ord('\t'): None, ord('@'): None, ord("'"): None, ord("’"): None,
                       ord("Ö"): None}
        return value.translate(trans_table)

    def add_foreign_key(self, column_name, referenced_table, referenced_column, constraint_name=None):
        """
        Adds a foreign key to a specified column in the current table.

        :param column_name: The name of the column in the current table to become a foreign key.
        :param referenced_table: The name of the table which the foreign key references.
        :param referenced_column: The name of the column in the referenced table.
        :param constraint_name: Optional name for the foreign key constraint.
        """
        # Check if the column exists in the current table
        if column_name not in self.columns:
            print(f"Error: Column '{column_name}' does not exist in table '{self.table_name}'. Operation aborted.")
            return False

        # Check if the referenced table and column exist
        if not self._check_column_exists(referenced_table, referenced_column):
            print(
                f"Error: Referenced column '{referenced_column}' does not exist in table '{referenced_table}'. Operation aborted.")
            return False

        # If no constraint name is provided, generate one
        if not constraint_name:
            constraint_name = f"fk_{self.table_name}_{column_name}_{referenced_table}_{referenced_column}"

        # SQL to add the foreign key
        sql = f"""
        ALTER TABLE {self.table_name}
        ADD CONSTRAINT `{constraint_name}`
        FOREIGN KEY (`{column_name}`) REFERENCES `{referenced_table}`(`{referenced_column}`);
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            self.connection.commit()
            print(f"Foreign key added: {column_name} -> {referenced_table}({referenced_column})")
            return True
        except Exception as e:
            print(f"Failed to add foreign key: {str(e)}")
            return False
        finally:
            cursor.close()

    def _check_column_exists(self, table_name, column_name):
        """
        Checks if a column exists in the specified table.
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SHOW COLUMNS FROM `{table_name}` LIKE '{column_name}'")
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def print_table_info(self):
        """
        Prints detailed information about the table, including its structure, number of rows,
        database name, and foreign keys.
        """
        # Print basic table information
        print(f"Information for table '{self.table_name}':")

        # Table structure
        print("\nTable Structure:")
        self.print_table_structure()

        # Number of rows
        num_rows = self.count_rows()
        print(f"\nNumber of Rows: {num_rows}")

        # Database name
        print(f"\nDatabase Name: {self.db_config['database']}")

        # Foreign keys
        print("\nForeign Keys:")
        self.print_foreign_keys()

    def print_table_structure(self):
        """
        Prints the structure of the table (columns and their types).
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"DESCRIBE {self.table_name}")
            columns = cursor.fetchall()
            for column in columns:
                print(f"{column[0]} ({column[1]})")
        finally:
            cursor.close()

    def print_foreign_keys(self):
        """
        Prints the foreign key constraints of the table.
        """
        cursor = self.connection.cursor()
        try:
            # The specific SQL might vary depending on the RDBMS used; the example given is for MySQL.
            cursor.execute(f"""
            SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_NAME = '{self.table_name}' AND TABLE_SCHEMA = '{self.db_config['database']}'
            AND REFERENCED_TABLE_NAME IS NOT NULL;
            """)
            fks = cursor.fetchall()
            if fks:
                for fk in fks:
                    print(f"{fk[0]}: {fk[1]} references {fk[2]}({fk[3]})")
            else:
                print("No foreign keys.")
        finally:
            cursor.close()

    def check_fulltext_index(self, columns):
        """
        Проверяет, есть ли полнотекстовый индекс в заданных столбцах таблицы.
        :param cursor: объект курсора MySQL
        :param table_name: имя таблицы
        :param columns: список столбцов для проверки индекса
        :return: True если индекс существует, False если нет
        """
        # SQL-запрос для получения информации об индексах
        query = f"SHOW INDEX FROM {self.table_name};"
        cursor = self.connection.cursor()
        cursor.execute(query)
        indexes = cursor.fetchall()

        # Преобразуем полученные данные для удобства поиска
        index_columns = {}
        for index in indexes:
            index_name = index[2]  # имя индекса
            column_name = index[4]  # имя столбца
            index_type = index[10]  # тип индекса (FULLTEXT)

            if index_type == 'FULLTEXT':
                if index_name not in index_columns:
                    index_columns[index_name] = []
                index_columns[index_name].append(column_name)

        # Проверяем, есть ли полнотекстовый индекс для заданных столбцов
        for index_name, index_col_list in index_columns.items():
            if all(col in index_col_list for col in columns):
                print(f"Полнотекстовый индекс '{index_name}' найден для столбцов: {', '.join(columns)}.")
                return True

        print(f"Полнотекстовый индекс для столбцов: {', '.join(columns)} не найден.")
        return False

    def search_fulltext(self, columns, keyword):
        """
        Выполняет полнотекстовый поиск по заданным столбцам.
        :param cursor: объект курсора MySQL
        :param table_name: имя таблицы
        :param columns: список столбцов для поиска
        :param keyword: ключевое слово для поиска
        :return: список результатов
        """
        if self.check_fulltext_index(columns):
            # Если индекс существует, выполняем полнотекстовый поиск
            column_str = ", ".join(columns)
            query = f"""
            SELECT {column_str}
            FROM {self.table_name}
            WHERE MATCH({column_str}) AGAINST(%s IN NATURAL LANGUAGE MODE);
            """
            cursor = self.connection.cursor()
            cursor.execute(query, (keyword,))
            results = cursor.fetchall()

            if results:
                for row in results:
                    print(row)
            else:
                print("По вашему запросу ничего не найдено.")
        else:
            print("Полнотекстовый индекс отсутствует, поиск невозможен.")

    def fetch_all_as_json(self):
        """
        Извлекает все данные из таблицы и преобразует их в список объектов JSON.

        :return: Список строк в формате JSON
        """
        # SQL запрос для получения всех данных из таблицы
        query = f"SELECT * FROM {self.table_name}"

        # Выполняем запрос и получаем результат в виде Pandas DataFrame
        df = self._execute_query(query)

        # Преобразуем строки DataFrame в список словарей
        records = df.to_dict(orient='records')

        # Преобразуем каждый словарь в строку JSON
        json_objects = [json.dumps(record) for record in records]

        return json_objects

    def fetch_filtered_as_json(self, where_clause='', columns='*'):
        """
        Извлекает данные из таблицы на основе условия и преобразует их в список объектов JSON.

        :param where_clause: Условие для SQL-запроса (например, 'WHERE age > 30').
        :param columns: Список колонок для выборки (например, 'name, age'), по умолчанию '*'.
        :return: Список строк в формате JSON.
        """
        # Формируем SQL запрос с учетом фильтра (where_clause)
        query = f"SELECT {columns} FROM {self.table_name} {where_clause}"

        # Выполняем запрос и получаем результат в виде DataFrame
        df = self._execute_query(query)

        # Преобразуем строки DataFrame в список словарей
        records = df.to_dict(orient='records')

        # Преобразуем каждый словарь в строку JSON
        json_objects = [json.dumps(record) for record in records]

        return json_objects

    def insert_json_objects_as_string(self, json_objects, column_name):
        """
        Вставляет каждый JSON объект целиком в одну ячейку указанного столбца таблицы.

        :param json_objects: Список JSON объектов для загрузки.
        :param column_name: Название столбца, в который нужно загрузить данные.
        """
        # SQL запрос для вставки данных в таблицу
        query = f"INSERT INTO {self.table_name} ({column_name}) VALUES (%s)"

        # Подключаемся к базе данных и вставляем данные
        cursor = self.connection.cursor()
        try:
            for json_object in json_objects:
                # Преобразуем JSON объект в строку, если это не строка
                if isinstance(json_object, dict):
                    json_str = json.dumps(json_object)  # Преобразование Python словаря в строку JSON
                else:
                    json_str = json_object  # Если это уже строка, используем как есть

                # Вставляем JSON строку в базу данных
                cursor.execute(query, (json_str,))
            self.connection.commit()
        finally:
            cursor.close()

    def update_columns_from_json(self, json_column, id_column, columns_to_extract):
        """
        Считывает JSON объекты из указанного столбца, извлекает значения для указанных колонок,
        и обновляет таблицу на основе ID, устанавливая новые значения для этих колонок.

        :param json_column: Название столбца, из которого будут извлекаться JSON объекты.
        :param id_column: Название столбца, содержащего уникальный идентификатор (например, 'id').
        :param columns_to_extract: Список колонок, значения которых нужно извлечь из JSON объектов.
        """
        # 1. Считать все записи из таблицы, включая JSON объекты и идентификатор
        query = f"SELECT {id_column}, {json_column} FROM {self.table_name}"
        rows = self._execute_query(query)

        # 2. Подготовить запрос для обновления значений
        set_clause = ', '.join([f"{col} = %s" for col in columns_to_extract])
        update_query = f"UPDATE {self.table_name} SET {set_clause} WHERE {id_column} = %s"

        cursor = self.connection.cursor()

        try:
            for row in rows.itertuples(index=False):
                record_id = getattr(row, id_column)
                json_data = getattr(row, json_column)

                try:
                    # 3. Преобразовать JSON строку в Python объект
                    json_obj = json.loads(json_data)
                except json.JSONDecodeError:
                    print(f"Ошибка декодирования JSON для записи с ID {record_id}")
                    continue

                # 4. Извлечь значения для указанных колонок
                values_to_update = [json_obj.get(col) for col in columns_to_extract]

                if None in values_to_update:
                    print(f"Не все данные найдены для записи с ID {record_id}, пропускаем.")
                    continue

                # 5. Выполнить обновление таблицы
                cursor.execute(update_query, (*values_to_update, record_id))

            # 6. Зафиксировать изменения в базе данных
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            print(f"Ошибка при обновлении данных: {e}")
        finally:
            cursor.close()

    def push_list(self, tags_list, column):
        """
        Pushes a list of tags into the tags table.

        :param tags_list: List of tags (strings) to insert into the table.
        """
        # Проход по списку тегов
        for tag in tags_list:
            # Проверка, существует ли уже такой тег в таблице
            existing_tag_df = self.select_where(f"WHERE '{column}' = '{tag}'")

            if existing_tag_df.empty:
                # Если тега нет, вставляем новый тег
                self.insert_row({f'{column}': tag})
            else:
                # Если тег уже существует, пропускаем или можно обновить (если нужно)
                print(f"Tag '{column}' already exists, skipping.")

    def __del__(self):
        """
        Destructor to ensure that the cursor and connection are closed.
        """
        try:
            if self.cursor is not None:
                self.cursor.close()
            if self.connection is not None:
                self.connection.close()
        except ReferenceError:
            # Handle the case where the object no longer exists
            pass
        except Exception as e:
            print(f"Error closing database resources: {e}")



# Example usage:
