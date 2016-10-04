#!/usr/bin/python
"""
Copyright 2015 INTEL RESEARCH AND INNOVATION IRELAND LIMITED

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import ez_setup
import setuptools


ez_setup.use_setuptools()

setuptools.setup(
    name="adaptation-engine-framework",
    version="1.1.0",
    description="Adaptation Engine framework",
    author="Intel - Daniel Doyle",
    author_email="danielx.doyle@intel.com",
    download_url="",
    keywords=["adaptation", "engine", "framework"],
    license='Apache License 2.0',
    install_requires=[
        'pika',
        'pymongo',
        'jpype1',
        'requests',
        'python-keystoneclient==1.7.2',
        'python-novaclient==2.30.1',
        'python-heatclient==1.0.0',
        'web.py',
    ],
    packages=setuptools.find_packages('src'),
    package_dir={'': 'src'},
    package_data={
        '': ['*.yaml'],
    },
    tests_require=[
        'mock',
        'nose',
        'coverage',
        'pep8',
        'pylint'
    ],
    entry_points={
        'console_scripts': [
            (
                'adaptationengine='
                'adaptationengine_framework.adaptationengine:main'
            ),
            (
                'adaptationengine-plugintester='
                'adaptationengine_plugintester.harness:main'
            ),
        ],
    }
)
