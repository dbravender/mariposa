from mariposa import __version__
from setuptools import setup

setup(
    name='mariposa',
    version=__version__,
    description='Safely and automatically migrate database schemas',
    author='Dan Bravender',
    author_email='dan.bravender@gmail.com',
    entry_points={'console_scripts': ['mariposa = mariposa.core:main']},
    packages=['mariposa'],
)
