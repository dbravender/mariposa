from dbmigrate.core import (
    DBMigrate, OutOfOrderException, ModifiedMigrationException
)
from dbmigrate.dbengines import loads_string_keys
import subprocess
import os

import unittest


class FakeFile(object):
    def __call__(self, filename, options):
        self.filename = filename
        self.options = options
        return self

    def write(self, contents):
        self.contents = contents


class TestDBMigrate(unittest.TestCase):
    def setUp(self):
        engine = os.environ.get('DBMIGRATE_ENGINE', 'sqlite')
        connection_string = os.environ.get('DBMIGRATE_CONNECTION', ':memory:')
        connection_settings = loads_string_keys(connection_string)
        self.settings = {
            'out_of_order': False,
            'dry_run': False,
            'engine': engine,
            'connection_string': connection_string,
        }
        if engine == 'mysql':
            import MySQLdb
            # create the test database
            db = connection_settings.pop('db')
            c = MySQLdb.connect(**connection_settings)
            c.cursor().execute('DROP DATABASE IF EXISTS %s' % db)
            c.cursor().execute('CREATE DATABASE %s' % db)
        if engine == 'postgres':
            import psycopg2
            # create the test database
            database = connection_settings['database']
            schema = connection_settings.pop('schema', None)

            if schema is None:
                c = psycopg2.connect(database='template1')
                c.set_isolation_level(0)
                cur = c.cursor()
                cur.execute('DROP DATABASE IF EXISTS %s' % database)
                cur.execute('CREATE DATABASE %s' % database)

            else:
                c = psycopg2.connect(**connection_settings)
                c.cursor().execute('DROP SCHEMA IF EXISTS %s CASCADE' % schema)
                c.cursor().execute('CREATE SCHEMA %s' % schema)
                c.commit()

    def test_create(self):
        self.settings['directory'] = '/tmp'
        dbmigrate = DBMigrate(**self.settings)
        fake_file = FakeFile()
        dbmigrate.create('test slug', 'sql', fake_file)
        self.assert_(fake_file.filename.startswith('/tmp'))
        self.assert_(fake_file.filename.endswith('test-slug.sql'))
        self.assertEqual(fake_file.contents, '-- add your migration here')

    def test_current_migrations(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        dbmigrate = DBMigrate(**self.settings)
        self.assertEqual(
            dbmigrate.current_migrations(), [(
                '20120115075349-create-user-table.sql',
                '0187aa5e13e268fc621c894a7ac4345579cf50b7'
            )])

    def test_dry_run_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        self.settings['dry_run'] = True
        dbmigrate = DBMigrate(**self.settings)
        self.assertEqual(dbmigrate.migrate(), (
            "sql: -- start filename: 20120115075349-create-user-table.sql "
            "sha1: 0187aa5e13e268fc621c894a7ac4345579cf50b7\n"
            "-- intentionally making this imperfect so it can be migrated\n"
            "CREATE TABLE users (\n"
            "  id int PRIMARY KEY,\n"
            "  name varchar(255),\n"
            "  password_sha1 varchar(40)\n"
            ");\n"
            "INSERT INTO dbmigration (filename, sha1, date) VALUES ("
            "'20120115075349-create-user-table.sql', "
            "'0187aa5e13e268fc621c894a7ac4345579cf50b7', %s());" %
            dbmigrate.engine.date_func))

    def test_multiple_migration_dry_run(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'second-run')
        self.settings['directory'] = fixtures_path
        self.settings['dry_run'] = True
        dbmigrate = DBMigrate(**self.settings)
        self.assertEqual(dbmigrate.migrate(), (
            "sql: -- start filename: 20120115075349-create-user-table.sql "
            "sha1: 0187aa5e13e268fc621c894a7ac4345579cf50b7\n"
            "-- intentionally making this imperfect so it can be migrated\n"
            "CREATE TABLE users (\n"
            "  id int PRIMARY KEY,\n"
            "  name varchar(255),\n"
            "  password_sha1 varchar(40)\n"
            ");\n"
            "INSERT INTO dbmigration (filename, sha1, date) VALUES ("
            "'20120115075349-create-user-table.sql', "
            "'0187aa5e13e268fc621c894a7ac4345579cf50b7', "
            "%(date_func)s());\n"
            "sql: -- start filename: 20120603133552-awesome.sql sha1: "
            "6759512e1e29b60a82b4a5587c5ea18e06b7d381\n"
            "ALTER TABLE users ADD COLUMN email varchar(70);\n"
            "INSERT INTO dbmigration (filename, sha1, date) VALUES ("
            "'20120603133552-awesome.sql', "
            "'6759512e1e29b60a82b4a5587c5ea18e06b7d381', %(date_func)s());" %
            {'date_func': dbmigrate.engine.date_func}))

    def test_initial_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        # since the database is in memory we need to reach in to get it
        self.assertEqual(
            dbmigrate.engine.performed_migrations(), [(
                '20120115075349-create-user-table.sql',
                '0187aa5e13e268fc621c894a7ac4345579cf50b7'
            )])

    def test_out_of_order_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'out-of-order-1')
        self.settings['directory'] = fixtures_path
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        dbmigrate.directory = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'out-of-order-2')
        try:
            dbmigrate.migrate()
            self.fail('Expected an OutOfOrder exception')
        except OutOfOrderException as e:
            self.assertEqual(
                str(e),
                ('[20120114221757-before-initial.sql] '
                 'older than the latest performed migration'))

    def test_allowed_out_of_order_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'out-of-order-1')
        self.settings['directory'] = fixtures_path
        self.settings['out_of_order'] = True
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        dbmigrate.directory = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'out-of-order-2')
        dbmigrate.migrate()
        self.assertEqual(
            dbmigrate.engine.performed_migrations(),
            [('20120114221757-before-initial.sql',
              'c7fc17564f24f7b960e9ef3f6f9130203cc87dc9'),
             ('20120115221757-initial.sql',
              '841ea60d649264965a3e8c8a955fd7aad54dad3e')])

    def test_modified_migrations_detected(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'modified-1')
        self.settings['directory'] = fixtures_path
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        dbmigrate.directory = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'modified-2')
        try:
            dbmigrate.migrate()
            self.fail('Expected a ModifiedMigrationException')
        except ModifiedMigrationException as e:
            self.assertEqual(
                str(e),
                ('[20120115221757-initial.sql] migrations were '
                 'modified since they were run on this database.'))

    def test_deleted_migrations_detected(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'deleted-1')
        self.settings['directory'] = fixtures_path
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        dbmigrate.directory = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'deleted-2')
        try:
            dbmigrate.migrate()
            self.fail('Expected a ModifiedMigrationException')
        except ModifiedMigrationException as e:
            self.assertEqual(
                str(e),
                ('[20120115221757-initial.sql] migrations were '
                 'deleted since they were run on this database.'))

    def test_multiple_migrations(self):
        self.settings['directory'] = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        dbmigrate.directory = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'second-run')
        dbmigrate.migrate()
        self.assertEqual(
            dbmigrate.engine.performed_migrations(),
            [('20120115075349-create-user-table.sql',
              '0187aa5e13e268fc621c894a7ac4345579cf50b7'),
             ('20120603133552-awesome.sql',
              '6759512e1e29b60a82b4a5587c5ea18e06b7d381')])

    def test_null_migration_after_successful_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        self.settings['out_of_order'] = False
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        dbmigrate.migrate()

    def test_null_dry_run_migration(self):
        self.settings['directory'] = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'second-run')
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        self.settings['dry_run'] = True
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()

    def test_passing_script_migration(self):
        self.settings['directory'] = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'arbitrary-scripts')
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        self.assertEqual(
            dbmigrate.engine.performed_migrations(),
            [('20121019152404-initial.sql',
              '4205e6d2f0c0f141098ccf8b56e04ed2e9da3f92'),
             ('20121019152409-script.sh',
              '837a6ab019646fae8488048e20ff2651437b2fbd'),
             ('20121019152412-final.sql',
              '4205e6d2f0c0f141098ccf8b56e04ed2e9da3f92')])

    def test_failing_script_migration(self):
        self.settings['directory'] = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'arbitrary-scripts-failing')
        dbmigrate = DBMigrate(**self.settings)
        try:
            dbmigrate.migrate()
            self.fail('Expected the script to fail')
        except subprocess.CalledProcessError as e:
            self.assert_('20121019152409-script.sh' in str(e))

    def test_ignore_filenames_sha1_migration(self):
        self.settings['directory'] = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'sha1-update-1')
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        dbmigrate.directory = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'sha1-update-2')
        dbmigrate.renamed()
        dbmigrate.migrate()
        self.assertEqual(
            dbmigrate.engine.performed_migrations(),
            [('20120115075300-add-another-test-table-renamed-reordered.sql',
              '4aebd2514665effff5105ad568a4fbe62f567087'),
             ('20120115075349-create-user-table.sql',
              '0187aa5e13e268fc621c894a7ac4345579cf50b7')])
