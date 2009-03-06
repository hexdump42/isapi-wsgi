
try:
	from setuptools import setup
except ImportError:
	from distutils.core import setup
 
try:
	from distutils.command.build_py import build_py_2to3 as build_py
except ImportError:
	from distutils.command.build_py import build_py

try:
	from distutils.command.build_scripts import build_scripts_2to3 as build_scripts
except ImportError:
	from distutils.command.build_scripts import build_scripts

# Load the reStructuredText document from docs
import os
this_dir = os.path.dirname(__file__)
doc_file = os.path.join(this_dir, 'docs', 'ABOUT.txt')
long_description = open(doc_file).read()
changes = os.path.join(this_dir, 'CHANGES.txt')
long_description += open(changes).read()

# PyPI will use rst2html from docutils to convert ABOUT.txt to HTML

setup(name='isapi_wsgi',
	version='0.3',
	description='A WSGI handler for ISAPI',
	long_description=long_description,
	author='Mark Rees',
	author_email='mark dot john dot rees at gmail dot com',
	url = "code.google.com/p/isapi-wsgi",
	license='MIT',
	py_modules=['isapi_wsgi'],
	packages=['tests'],
	cmdclass = {'build_py':build_py,
	            'build_scripts':build_scripts,
	           }
	)
