import collections
import logging
import sqlite3
import os
try:
    import json
except ImportError:
    import simplejson as json


logger = logging.getLogger(__name__)


loads_string_keys = lambda s: dict(
    (str(k), v) for k, v in json.loads(s).items()
)


class SQLException(Exception):
    pass


FilenameSha1 = collections.namedtuple('FilenameSha1', 'filename sha1')


class DatabaseMigrationEngine(object):
    migration_table_sql = (
        "CREATE TABLE dbmigration "
        "(filename varchar(255), sha1 varchar(40), date datetime);")

    def create_migration_table(self):
        self.execute(self.migration_table_sql)

    def sql(self, directory, files_sha1s_to_run):
        for filename, sha1 in sorted(files_sha1s_to_run):
            command = None
            sql_statements = []
            sql_statements.append(
                '-- start filename: %s sha1: %s' % (filename, sha1))
            if os.path.splitext(filename)[-1] == '.sql':
                sql_statements += file(
                    os.path.join(directory, filename)).read().splitlines()
            else:
                command = os.path.join(directory, filename)
            sql_statements.append(
                "INSERT INTO dbmigration (filename, sha1, date) "
                "VALUES ('%s', '%s', %s());" %
                (filename, sha1, self.date_func))
            yield command, "\n".join(sql_statements)

    def performed_migrations(self):
        return [FilenameSha1(r[0], r[1]) for r in self.results(
            "SELECT filename, sha1 FROM dbmigration ORDER BY filename")]


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
        self.connection = self.engine.connect(
            **loads_string_keys(connection_string)
        )
        self.ProgrammingError = self.engine.ProgrammingError
        self.OperationalError = self.engine.OperationalError

    def execute(self, statement):
        try:
            c = self.connection.cursor()
            c.execute(statement)
            return c
        except (self.ProgrammingError, self.OperationalError) as e:
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

    migration_table_sql = (
        "CREATE TABLE dbmigration "
        "(filename varchar(255), sha1 varchar(40), date timestamp);")

    def __init__(self, connection_string):
        import psycopg2
        self.engine = psycopg2
        connection_dict = json.loads(connection_string)
        schema = connection_dict.pop('schema', None)
        super(postgres, self).__init__(json.dumps(connection_dict))
        if schema:
            self.execute('SET search_path = %s' % schema)

    def execute(self, statement):
        try:
            c = self.connection.cursor()
            c.execute(statement)
            self.connection.commit()
            return c
        except (self.ProgrammingError, self.OperationalError) as e:
            self.connection.rollback()
            raise SQLException(str(e))
