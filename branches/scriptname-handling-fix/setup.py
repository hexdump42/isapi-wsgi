
from distutils.core import setup

try:
	from distutils.command.build_py import build_py_2to3 as build_py
except ImportError:
	from distutils.command.build_py import build_py

try:
	from distutils.command.build_scripts import build_scripts_2to3 as build_scripts
except ImportError:
	from distutils.command.build_scripts import build_scripts

setup(name='isapi_wsgi',
	version='0.3',
	description='A WSGI handler for ISAPI',
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
