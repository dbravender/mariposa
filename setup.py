from dbmigrate import __version__
from distutils.core import setup

setup(
    name='dbmigrate',
    version=__version__,
    description='Safely and automatically migrate database schemas',
    author='Dan Bravender',
    author_email='dan.bravender@gmail.com',
    scripts=['bin/dbmigrate'],
    packages=['dbmigrate'],
)
