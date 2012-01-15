from dbmigrate import DBMigrate
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
        assert dbmigrate.migrate() == """BEGIN;
-- start filename: 20120115075349-create-user-table.sql sha1: 00fe6624203fd0be1a6d359bf01341f18d325834
-- intentionally making this imperfect so it can be migrated
CREATE TABLE users (
  id int AUTO_INCREMENT PRIMARY KEY,
  name varchar(255),
  password_sha1 varchar(40)
);
INSERT INTO dbmigration (filename, sha1, date) VALUES ('20120115075349-create-user-table.sql', '00fe6624203fd0be1a6d359bf01341f18d325834', datetime());
COMMIT;"""
