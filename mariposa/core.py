from mariposa.command import command
from hashlib import sha1
from optparse import OptionParser
from datetime import datetime
from glob import glob
import subprocess
import logging
import os
import sys
from mariposa import dbengines
from mariposa.dbengines import FilenameSha1


logger = logging.getLogger(__name__)


class OutOfOrderException(Exception):
    pass


class ModifiedMigrationException(Exception):
    pass


class DBMigrate(object):
    """A set of commands to safely migrate databases automatically"""
    def __init__(self, out_of_order, dry_run, engine, connection_string,
                 directory):
        self.out_of_order = out_of_order
        self.dry_run = dry_run
        self.engine = getattr(dbengines, engine)(connection_string)
        self.directory = directory

    def blobsha1(self, filename):
        """returns the git sha1sum of a file so the exact migration
        that was run can easily be looked up in the git history"""
        text = open(filename).read()
        s = sha1(("blob %u\0" % len(text)).encode('UTF-8'))
        s.update(text.encode('UTF-8'))
        return s.hexdigest()

    def current_migrations(self):
        """returns the current migration files as a list of
           (filename, sha1sum) tuples"""
        return [
            FilenameSha1(os.path.basename(filename), self.blobsha1(filename))
            for filename in glob(os.path.join(self.directory, '*'))]

    def warn(self, message):
        sys.stderr.write(message + "\n")

    @command
    def renamed(self, *args):
        """rename files in the migration table if the order changed"""
        performed_migrations = dict(
            (v, k) for k, v in self.engine.performed_migrations())
        current_migrations = dict(
            (v, k) for k, v in self.current_migrations())
        renames = []
        for sha1, old_filename in performed_migrations.items():
            new_filename = current_migrations.get(sha1)
            if sha1 in current_migrations and old_filename != new_filename:
                renames.append(FilenameSha1(new_filename, sha1))
        sql = '\n'.join(
            "UPDATE dbmigration SET filename = '%(filename)s' "
            "WHERE sha1 = '%(sha1)s';" % rename._asdict()
            for rename in renames)
        if self.dry_run:
            return sql
        else:
            self.engine.execute(sql)

    @command
    def migrate(self, *args):
        """migrate a database to the current schema"""
        if not self.dry_run:
            try:
                self.engine.create_migration_table()
            except dbengines.SQLException:
                # migration table has already been created
                pass
        try:
            performed_migrations = self.engine.performed_migrations()
        except dbengines.SQLException as e:
            if self.dry_run:
                # corner case - dry run on a database without a migration table
                performed_migrations = []
            else:
                raise e

        current_migrations = self.current_migrations()
        files_current = [x.filename for x in current_migrations]
        files_performed = [x.filename for x in performed_migrations]
        files_sha1s_to_run = (
            set(current_migrations) - set(performed_migrations))
        files_to_run = [x.filename for x in files_sha1s_to_run]
        if len(files_performed):
            latest_migration = max(files_performed)
            old_unrun_migrations = list(filter(
                lambda f: f < latest_migration, files_to_run))
            if len(old_unrun_migrations):
                if self.out_of_order:
                    self.warn('Running [%s] out of order.' %
                              ','.join(old_unrun_migrations))
                else:
                    raise OutOfOrderException(
                        '[%s] older than the latest performed migration' %
                        ','.join(old_unrun_migrations))
        modified_migrations = set(files_to_run).intersection(files_performed)
        if modified_migrations:
            raise ModifiedMigrationException(
                '[%s] migrations were modified since they were '
                'run on this database.' % ','.join(modified_migrations))
        deleted_migrations = (
            set(files_performed + files_to_run) - set(files_current))
        if deleted_migrations:
            raise ModifiedMigrationException(
                '[%s] migrations were deleted since they were '
                'run on this database.' % ','.join(deleted_migrations))
        command_sql = self.engine.sql(self.directory, files_sha1s_to_run)
        if self.dry_run:
            response = []
            for command, sql in command_sql:
                if command:
                    response.append('command: ' + command)
                if sql:
                    response.append('sql: ' + sql)
            return '\n'.join(response)
        else:
            for command, sql in command_sql:
                if command:
                    subprocess.check_call(command)
                if sql:
                    self.engine.execute(sql)

    @command
    def create(self, slug, ext="sql", open=open):
        """create a new migration file"""
        dstring = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        slug = "-".join(slug.split(" "))
        filename = os.path.join(self.directory, '%s-%s.%s' %
                                (dstring, slug, ext))
        if self.dry_run:
            return 'Would create %s' % filename
        else:
            open(filename, 'w').write('-- add your migration here')


def main():
    usage = '\n'
    for command_name, help in sorted(command.help.iteritems()):
        usage += "%s - %s\n" % (command_name.rjust(15), help)

    parser = OptionParser(usage=usage)

    parser.add_option(
        "-o", "--out-of-order", dest="out_of_order", action="store_true",
        help="allow migrations to be run out of order",
        default=False)
    parser.add_option(
        "-n", "--dry-run", dest="dry_run", action="store_true",
        help="print SQL that would be run but take no real action",
        default=False)
    parser.add_option(
        "-e", "--engine", dest="engine", action="store",
        help="database engine",
        default="sqlite",
        type="string")
    parser.add_option(
        "-c", "--connection-string", dest="connection_string", action="store",
        help="string used by the database engine to connect to the database",
        default=":memory:",
        type="string")
    parser.add_option(
        "-d", "--directory", dest="directory", action="store",
        help="directory where the migrations are stored",
        type="string",
        default=".")

    (options, args) = parser.parse_args()

    if not len(args):
        parser.print_help()
    else:
        options = vars(options)
        options['engine'] = os.environ.get(
            'DBMIGRATE_ENGINE', options['engine'])
        options['connection_string'] = os.environ.get(
            'DBMIGRATE_CONNECTION', options['connection_string'])
        mariposa = DBMigrate(**options)
        result = command.commands[args[0]](mariposa, *args[1:])
        if result:
            print(result)


if __name__ == '__main__':
    main()
