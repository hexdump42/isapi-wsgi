
from distutils.core import setup

setup(name='isapi_wsgi',
	version='0.3',
	description='A WSGI handler for ISAPI',
	author='Mark Rees',
	author_email='mark dot john dot rees at gmail dot com',
	url = "code.google.com/p/isapi-wsgi",
	license='MIT',
	py_modules=['isapi_wsgi'],
	packages=['tests']
	)
