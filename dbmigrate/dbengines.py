import logging


logger = logging.getLogger(__name__)


class SQLException(Exception):
    pass


class DatabaseMigrationEngine(object):
    def __init__(self, connection_string):
        self.connection_string = connection_string

    def create_migration_table(self):
        try:
            self.execute(
                "CREATE TABLE dbmigration "
                "(filename varchar(255), sha1 varchar(40), date datetime);")
        except SQLException:
            logger.log('Could not create the migration table')

    def sql(self, files_to_run):
        commands = ['BEGIN;']
        for filename, sha1 in files_to_run:
            commands.append(
                '-- start filename: %s sha1: %s' % (filename, sha1))
            commands += file(filename).read().splitlines()
            commands.append(
                "INSERT INTO dbmigration (filename, sha1, date) "
                "VALUES ('%s', '%s', %s())" % (filename, sha1, self.date_func))
        commands.append('COMMIT;')
        return "\n".join(commands)

    def migration_status(self):
        return self.results("SELECT filename, sha1, date FROM dbmigration")


class sqlite(DatabaseMigrationEngine):
    """a migration engine for sqlite"""
    date_func = 'datetime'


class mysql(DatabaseMigrationEngine):
    """a migration engine for mysql"""
    date_func = 'now'
