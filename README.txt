= ISAPI_WSGI ISAPISimpleHandler Beta =


== Dependencies ==

 * Python 2.2+
 * Python win32 extensions that include the isapi package
 * wsgiref library from http://cvs.eby-sarna.com/wsgiref/
 * A windows webserver that supports ISAPI (isapi_wsgi to-date has only been tested on IIS 5.1)

== Installation ==

Python 2.2 or better is required.  To install, just unpack the archive, go to the directory containing 'setup.py', and run::

python setup.py install

isapi_wsgi.py will be installed in the 'site-packages' directory of your Python
installation.  (Unless directed elsewhere; see the "Installing Python
Modules" section of the Python manuals for details on customizing
installation locations, etc.).

(Note: for the Win32 installer release, just run the .exe file.)

== Limitations ==

 * Single threaded

== Usage ==

See the mainline in isapi_wsgi.py or the samples in the examples subdirectory.

Running the command:

python isapi_wsgi.py 

will create a simple ISAPI test extension that can be accessed from a webbrowser using the url:

http://localhost/isapi-wsgi-test/test

Examples

 * demo.py - app that displays a hello world and the wsgi environment.

 * echo.py - the test app from wsgi webkit. Used for isapi_wsgi unit tests.

 * multiple_apps.py - show how to support multiple wsgi apps from one isapi extension.

 * qwip_test.py - run quixote.demo as a WSGI app using QWIP.

Also it is worthwhile reading the docs that come with the win32 isapi extension.

== Debugging ==

A simple trace function is provided that will allow viewing of print statements using win32traceutil if the isapi_wsgi traceon global is set to 1.

== To Do ==

Write fully threaded version

Add better error logging support

== Credits ==

Peter Hunt for initial code review and support.

Mark Hammonds win32 extensions which are doing all the hard work.

Phillip J. Eby for wsgiref which kept my implementation honest.

My wife and son for letting me spend some of their quality time working on this project.

