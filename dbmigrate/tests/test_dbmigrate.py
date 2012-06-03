from dbmigrate import (
    DBMigrate, OutOfOrderException, ModifiedMigrationException
)
import os
try:
    import json
except ImportError:
    import simplejson as json


class FakeFile(object):
    def __call__(self, filename, options):
        self.filename = filename
        self.options = options
        return self

    def write(self, contents):
        self.contents = contents


class TestDBMigrate(object):
    def setUp(self):
        engine = os.environ.get('DBMIGRATE_ENGINE', 'sqlite')
        connection_string = os.environ.get('DBMIGRATE_CONNECTION', ':memory:')
        self.settings = {
            'out_of_order': False,
            'dry_run': False,
            'engine': engine,
            'connection_string': connection_string,
        }
        if engine == 'mysql':
            import MySQLdb
            connection_settings = json.loads(connection_string)
            # create the test database
            db = connection_settings.pop('db')
            c = MySQLdb.connect(**connection_settings)
            c.cursor().execute('DROP DATABASE IF EXISTS %s' % db)
            c.cursor().execute('CREATE DATABASE %s' % db)
        if engine == 'postgres':
            import psycopg2
            connection_settings = json.loads(connection_string)
            # create the test database
            schema = connection_settings.pop('schema')
            c = psycopg2.connect(**connection_settings)
            c.cursor().execute('DROP SCHEMA IF EXISTS %s CASCADE' % schema)
            c.cursor().execute('CREATE SCHEMA %s' % schema)
            c.commit()

    def test_create(self):
        self.settings['directory'] = '/tmp'
        dbmigrate = DBMigrate(**self.settings)
        fake_file = FakeFile()
        dbmigrate.create(['test', 'slug'], fake_file)
        assert fake_file.filename.startswith('/tmp')
        assert fake_file.filename.endswith('test-slug.sql')
        assert fake_file.contents == '-- add your migration here'

    def test_current_migrations(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        dbmigrate = DBMigrate(**self.settings)
        assert dbmigrate.current_migrations() == [(
                '20120115075349-create-user-table.sql',
                '0187aa5e13e268fc621c894a7ac4345579cf50b7'
            )]

    def test_dry_run_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        self.settings['dry_run'] = True
        dbmigrate = DBMigrate(**self.settings)
        assert dbmigrate.migrate() == ("""BEGIN;
-- start filename: 20120115075349-create-user-table.sql sha1: """
"""0187aa5e13e268fc621c894a7ac4345579cf50b7
-- intentionally making this imperfect so it can be migrated
CREATE TABLE users (
  id int PRIMARY KEY,
  name varchar(255),
  password_sha1 varchar(40)
);
INSERT INTO dbmigration (filename, sha1, date) VALUES ("""
"""'20120115075349-create-user-table.sql', """
"""'0187aa5e13e268fc621c894a7ac4345579cf50b7', %s());
COMMIT;""" % dbmigrate.engine.date_func)

    def test_multiple_migration_dry_run(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'second-run')
        self.settings['directory'] = fixtures_path
        self.settings['dry_run'] = True
        dbmigrate = DBMigrate(**self.settings)
        assert dbmigrate.migrate() == ("""BEGIN;
-- start filename: 20120115075349-create-user-table.sql sha1: 0187aa5e13e268fc621c894a7ac4345579cf50b7
-- intentionally making this imperfect so it can be migrated
CREATE TABLE users (
  id int PRIMARY KEY,
  name varchar(255),
  password_sha1 varchar(40)
);
INSERT INTO dbmigration (filename, sha1, date) VALUES ('20120115075349-create-user-table.sql', '0187aa5e13e268fc621c894a7ac4345579cf50b7', %(date_func)s());
-- start filename: 20120603133552-awesome.sql sha1: 6759512e1e29b60a82b4a5587c5ea18e06b7d381
ALTER TABLE users ADD COLUMN email varchar(70);
INSERT INTO dbmigration (filename, sha1, date) VALUES ('20120603133552-awesome.sql', '6759512e1e29b60a82b4a5587c5ea18e06b7d381', %(date_func)s());
COMMIT;""" % {'date_func': dbmigrate.engine.date_func})

    def test_initial_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        # since the database is in memory we need to reach in to get it
        assert dbmigrate.engine.performed_migrations() == [(
            '20120115075349-create-user-table.sql',
            '0187aa5e13e268fc621c894a7ac4345579cf50b7'
        )]

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
            assert False, "Expected an OutOfOrder exception"
        except OutOfOrderException as e:
            assert str(e) == ('[20120114221757-before-initial.sql] '
                'older than the latest performed migration')

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
        assert dbmigrate.engine.performed_migrations() == [
            ('20120114221757-before-initial.sql',
             'c7fc17564f24f7b960e9ef3f6f9130203cc87dc9'),
            ('20120115221757-initial.sql',
             '841ea60d649264965a3e8c8a955fd7aad54dad3e')]

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
            assert False, 'Expected a ModifiedMigrationException'
        except ModifiedMigrationException as e:
            assert str(e) == ('[20120115221757-initial.sql] migrations were '
                'modified since they were run on this database.')

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
            assert False, 'Expected a ModifiedMigrationException'
        except ModifiedMigrationException as e:
            assert str(e) == ('[20120115221757-initial.sql] migrations were '
                'deleted since they were run on this database.')

    def test_multiple_migrations(self):
        self.settings['directory'] = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        dbmigrate.directory = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'second-run')
        dbmigrate.migrate()
        assert dbmigrate.engine.performed_migrations() == [
            ('20120115075349-create-user-table.sql',
             '0187aa5e13e268fc621c894a7ac4345579cf50b7'),
            ('20120603133552-awesome.sql',
             '6759512e1e29b60a82b4a5587c5ea18e06b7d381')]

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
