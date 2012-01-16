from dbmigrate import DBMigrate, OutOfOrderException
import os


class FakeFile(object):
    def __call__(self, filename, options):
        self.filename = filename
        self.options = options
        return self

    def write(self, contents):
        self.contents = contents


class TestDBMigrate(object):
    def setUp(self):
        self.settings = {
            'out_of_order': False,
            'dry_run': False,
            'engine': 'sqlite',
            'connection_string': ':memory:',
        }

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
                '00fe6624203fd0be1a6d359bf01341f18d325834'
            )]

    def test_dry_run_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        self.settings['dry_run'] = True
        dbmigrate = DBMigrate(**self.settings)
        assert dbmigrate.migrate() == ("""BEGIN;
-- start filename: 20120115075349-create-user-table.sql sha1: """
"""00fe6624203fd0be1a6d359bf01341f18d325834
-- intentionally making this imperfect so it can be migrated
CREATE TABLE users (
  id int AUTO_INCREMENT PRIMARY KEY,
  name varchar(255),
  password_sha1 varchar(40)
);
INSERT INTO dbmigration (filename, sha1, date) VALUES ("""
"""'20120115075349-create-user-table.sql', """
"""'00fe6624203fd0be1a6d359bf01341f18d325834', datetime());
COMMIT;""")

    def test_initial_migration(self):
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'initial')
        self.settings['directory'] = fixtures_path
        dbmigrate = DBMigrate(**self.settings)
        dbmigrate.migrate()
        # since the database is in memory we need to reach in to get it
        assert dbmigrate.engine.performed_migrations() == [(
            '20120115075349-create-user-table.sql',
            '00fe6624203fd0be1a6d359bf01341f18d325834'
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
