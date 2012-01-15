from command import command
from hashlib import sha1
from optparse import OptionParser
from datetime import datetime
from glob import glob
import logging
import os
import dbengines


logger = logging.getLogger(__name__)


class DBMigrate(object):
    """A set of commands to safely migrate databases automatically"""
    def __init__(
        self, out_of_order, dry_run, engine, connection_string, directory):
        self.out_of_order = out_of_order
        self.dry_run = dry_run
        self.engine = getattr(dbengines, engine)(connection_string)
        self.directory = directory

    def blobsha1(self, filename):
        """returns the git sha1sum of a file so the exact migration
        that was run can easily be looked up in the git history"""
        text = file(filename).read()
        s = sha1("blob %u\0" % len(text))
        s.update(text)
        return s.hexdigest()

    def current_migrations(self):
        """returns the current migration files as a list of
           (filename, sha1sum) tuples"""
        return [(os.path.basename(filename), self.blobsha1(filename))
            for filename in glob(os.path.join(self.directory, '*.sql'))]

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
        files_to_run = set(current_migrations) - set(performed_migrations)
        sql = self.engine.sql(self.directory, files_to_run)
        if self.dry_run:
            return sql
        else:
            self.engine.execute(sql)

    @command
    def create(self, slug, file=file):
        """create a new migration file"""
        filename = os.path.join(self.directory, '%s-%s.sql' % (
            datetime.utcnow().strftime('%Y%m%d%H%M%S'), ("-").join(slug)))
        if self.dry_run:
            print 'Would create %s' % filename
        else:
            file(filename, 'w').write('-- add your migration here')


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
        default="mysql",
        type="string")
    parser.add_option(
        "-c", "--connection-string", dest="connection_string", action="store",
        help="string used by the database engine to connect to the database",
        type="string")
    parser.add_option(
        "-d", "--directory", dest="directory", action="store",
        help="directory where the migrations are stored",
        type="string",
        default="dbmigrations")

    (options, args) = parser.parse_args()

    if not len(args):
        parser.print_help()
    else:
        dbmigrate = DBMigrate(**vars(options))
        result = command.commands[args[0]](dbmigrate, args[1:])
        if result:
            print(result)


if __name__ == '__main__':
    main()
