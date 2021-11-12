#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

requires = ['sphinx>2.0', 'lxml', 'sphinxcontrib-needs>=0.5.6']

setup(
    name='sphinx-test-reports',
    version='0.3.6',
    url='http://github.com/useblocks/sphinx-test-reports',
    download_url='http://pypi.python.org/pypi/sphinx-test-reports',
    license='MIT',
    author='team useblocks',
    author_email='info@useblocks.com',
    description='Sphinx extension for showing test results and test environment '
                'information inside sphinx documentations',
    long_description=open(os.path.join(os.path.dirname(__file__), "README.rst")).read(),
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Documentation',
        'Topic :: Utilities',
    ],
    platforms='any',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    namespace_packages=['sphinxcontrib'],
)
