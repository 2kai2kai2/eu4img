from os import getenv

import psycopg2
from dotenv import load_dotenv

load_dotenv("database.env")

conn: psycopg2.extensions.connection = psycopg2.connect(database=getenv("database"), user=getenv(
    "user"), password=getenv("password"), host=getenv("host"), port=getenv("port"))
conn.autocommit = True

cur: psycopg2.extensions.cursor = conn.cursor()
while True:
    command = input("> ")
    if command == "QUIT":
        cur.close()
        conn.close()
        quit()
    else:
        try:
            cur.execute(command)
            try:
                print(cur.fetchall())
            except psycopg2.ProgrammingError:
                pass
        except Exception as e:
            print(repr(e))
