#!/usr/bin/env python3

import sys

from setuptools import find_packages, setup

if sys.version_info.major < 3 or (
        sys.version_info.major == 3 and sys.version_info.minor < 6
):
    sys.exit("Python 3.6 or newer is required")

VERSION = 0.1

setup(
    name="cfggen",
    version=VERSION,
    description="Framework for generating configurations",
    author="Jakub Beránek",
    author_email="berykubik@gmail.com",
    url="https://github.com/kobzol/cfggen",
    packages=find_packages(),
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
