import logging
import sqlite3


logger = logging.getLogger(__name__)


class SQLException(Exception):
    pass


class DatabaseMigrationEngine(object):
    def create_migration_table(self):
        self.execute(
            "CREATE TABLE dbmigration "
            "(filename varchar(255), sha1 varchar(40), date datetime);")

    def sql(self, files_to_run):
        commands = ['BEGIN;']
        for filename, sha1 in files_to_run:
            commands.append(
                '-- start filename: %s sha1: %s' % (filename, sha1))
            commands += file(filename).read().splitlines()
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
        return self.execute(statement).fetchall()


class mysql(DatabaseMigrationEngine):
    """a migration engine for mysql"""
    date_func = 'now'
