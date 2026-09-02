import logging
import os
from pathlib import Path
from typing import TypedDict

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as PgConnection

from utils.logging_config import configure_logging

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
configure_logging()

logger = logging.getLogger(__name__)


class PostgresConfig(TypedDict):
    host: str
    port: int
    user: str
    password: str
    dbname: str


def db_config_from_env() -> PostgresConfig:
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD is not set in .env")
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": password,
        "dbname": os.getenv("POSTGRES_DB", "postgres"),
    }


class DatabaseUtil:

    def __init__(self):
        self.db_config = db_config_from_env()
        self.connection: PgConnection | None
        try: 
            self.connection = psycopg2.connect(**self.db_config) 

        except Exception as e:
            logger.error("Error connecting to the database: %s", e)
            self.connection = None

    def schema_details(self,schema_name):

        schema_info_context = ""
        
        connection = self.connection
        if connection is None:
            raise RuntimeError("Database connection is not available")
        cursor = connection.cursor()

        schema_info_context = f"Database Schema: {schema_name}\n"

        try: 

            cursor.execute("SELECT table_name from information_schema.tables where table_schema = %s;", (schema_name,))
            tables_list = cursor.fetchall()

            for table in tables_list:
                table_name = table[0]
                schema_info_context = f"{schema_info_context}\nTable: {table_name}\n"

                # Adding Columns & Data Types
                cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s;", (table_name,))
                columns_list = cursor.fetchall()

                for column in columns_list:
                    column_name = column[0]
                    data_type = column[1]
                    schema_info_context = f"{schema_info_context}  Column: {column_name}, Data Type: {data_type}\n"

                # Adding Sample Data
                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5;")
                sample_data = cursor.fetchall()
                schema_info_context = f"{schema_info_context}  Sample Data:\n"
                for row in sample_data:
                    schema_info_context = f"{schema_info_context}    {row}\n"

        except Exception as e:
            logger.error("Error fetching schema details: %s", e)
            schema_info_context = f"Error fetching schema details: {e}"

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
        
        return schema_info_context

    def execute_sql(self, query):
        connection = self.connection
        if connection is None:
            raise RuntimeError("Database connection is not available")
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
            connection.commit()
            return str(result)
        except Exception as e:
            logger.error("Error executing query: %s", e)
            return None
        finally:
            if cursor:
                cursor.close()
            connection.close()


if __name__ == "__main__":
    obj = DatabaseUtil()
    result = obj.schema_details("public")
    with open("test_schema_details.txt", "w") as f:
        f.write(result)