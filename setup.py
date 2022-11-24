# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
import os

here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the relevant file
# with open(path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
#    long_description = f.read()

long_description = ""

setup(
    name='st4sd-datastore',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='1.0.0',

    description='A tool for storing/querying metadata for experiments computed on multiple platforms',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.ibm.com/st4sd/st4sd-datastore',

    # Author details
    author='Vassilis Vassiliadis',
    author_email='vassilis.vassiliadis@ibm.com',

    # Choose your license
    license='IBM',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    # What does your project relate to?
    keywords='hpc workflows experiments analysis database explore plot query',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(".", exclude=['contrib', 'docs', 'tests*']),

    package_data={
    },

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    # entry_points={
    #    'console_scripts': [
    #        'sample=sample:main',
    #    ],
    # },

    scripts=[
        os.path.join('drivers', 'cluster_gateway.py'),
        os.path.join('drivers', 'reporter.py'),
        os.path.join('drivers', 'gateway_registry.py'),
        os.path.join('drivers', 'mongo_proxy.py'),
    ],

    install_requires=[
        'st4sd-runtime-core',
        'pymongo',
        'flask<=2.1.2', 'flask-restx', 'stream_zip', "six", "flask-cors", "werkzeug<=2.1.2",
    ],
)
