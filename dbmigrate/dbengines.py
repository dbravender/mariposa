import logging
import sqlite3
import os
try:
    import json
except ImportError:
    import simplejson as json


logger = logging.getLogger(__name__)


class SQLException(Exception):
    pass


class DatabaseMigrationEngine(object):
    migration_table_sql = ("CREATE TABLE dbmigration "
        "(filename varchar(255), sha1 varchar(40), date datetime);")

    def create_migration_table(self):
        self.execute(self.migration_table_sql)

    def sql(self, directory, files_sha1s_to_run):
        commands = ['BEGIN;']
        for filename, sha1 in sorted(files_sha1s_to_run):
            commands.append(
                '-- start filename: %s sha1: %s' % (filename, sha1))
            commands += file(
                os.path.join(directory, filename)).read().splitlines()
            commands.append(
                "INSERT INTO dbmigration (filename, sha1, date) "
                "VALUES ('%s', '%s', %s());" %
                    (filename, sha1, self.date_func))
        commands.append('COMMIT;')
        return "\n".join(commands)

    def performed_migrations(self):
        return self.results(
            "SELECT filename, sha1 FROM dbmigration ORDER BY filename")


class sqlite(DatabaseMigrationEngine):
    """a migration engine for sqlite"""
    date_func = 'datetime'

    def __init__(self, connection_string):
        self.connection = sqlite3.connect(connection_string)

    def execute(self, statement):
        try:
            return self.connection.executescript(statement)
        except sqlite3.OperationalError as e:
            raise SQLException(str(e))

    def results(self, statement):
        try:
            return self.connection.execute(statement).fetchall()
        except sqlite3.OperationalError as e:
            raise SQLException(str(e))


class GenericEngine(DatabaseMigrationEngine):
    """a generic database engine"""
    date_func = 'now'

    def __init__(self, connection_string):
        self.connection = self.engine.connect(**json.loads(connection_string))

    def execute(self, statement):
        try:
            c = self.connection.cursor()
            c.execute(statement)
            return c
        except (
            self.engine.ProgrammingError, self.engine.OperationalError) as e:
            self.connection.rollback()
            raise SQLException(str(e))

    def results(self, statement):
        return list(self.execute(statement).fetchall())


class mysql(GenericEngine):
    """a migration engine for mysql"""

    def __init__(self, connection_string):
        import MySQLdb
        self.engine = MySQLdb
        super(mysql, self).__init__(connection_string)


class postgres(GenericEngine):
    """a migration engine for postgres"""

    migration_table_sql = ("CREATE TABLE dbmigration "
        "(filename varchar(255), sha1 varchar(40), date timestamp);")

    def __init__(self, connection_string):
        import psycopg2
        self.engine = psycopg2
        connection_dict = json.loads(connection_string)
        schema = connection_dict.pop('schema')
        super(postgres, self).__init__(json.dumps(connection_dict))
        if schema:
            self.execute('SET search_path = %s' % schema)
