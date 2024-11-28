#!/usr/bin/env python

import os

from setuptools import find_namespace_packages, setup

requires = ["sphinx>=7.4.1", "lxml", "sphinx-needs>=4.0.0", "setuptools"]

with open(os.path.join(os.path.dirname(__file__), "README.rst")) as file:
    setup(
        name="sphinx-test-reports",
        # Update also test_reports.py, conf.py and changelog!
        version="1.1.0a",
        url="http://github.com/useblocks/sphinx-test-reports",
        download_url="http://pypi.python.org/pypi/sphinx-test-reports",
        license="MIT",
        author="team useblocks",
        author_email="info@useblocks.com",
        description="Sphinx extension for showing test results and test environment "
        "information inside sphinx documentations",
        long_description=file.read(),
        zip_safe=False,
        classifiers=[
            "Framework :: Sphinx",
            "Framework :: Sphinx :: Extension",
            "Development Status :: 4 - Beta",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Topic :: Documentation",
        ],
        platforms="any",
        packages=find_namespace_packages(include=['sphinxcontrib.*']),
        include_package_data=True,
        install_requires=requires,
        namespace_packages=["sphinxcontrib"],
    )
