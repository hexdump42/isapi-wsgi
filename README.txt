= ISAPI_WSGI Handler 0.4.2 =


== Dependencies ==

 * Python 2.3+
 * Python win32 extensions that include the isapi package
 * wsgiref library from http://cvs.eby-sarna.com/wsgiref/
 * A windows webserver that supports ISAPI
    (isapi_wsgi to-date has been tested on IIS 5.1 & 6)

== Installation ==

Python 2.3 or better is required.  To install, just unpack the archive, go to the
directory containing 'setup.py', and run::

python setup.py install

isapi_wsgi.py will be installed in the 'site-packages' directory of your Python
installation.  (Unless directed elsewhere; see the "Installing Python
Modules" section of the Python manuals for details on customizing
installation locations, etc.).

(Note: for the Win32 installer release, just run the .exe file.)

== Usage ==

See the mainline in isapi_wsgi.py or the samples in the examples subdirectory.

Running the command:

python isapi_wsgi.py 

will create a simple ISAPI test extension that can be accessed from a
webbrowser using the url:

http://localhost/isapi-wsgi-test/test

Examples

 * demo.py - app that displays a hello world and the wsgi environment using
   ISAPISimpleHandler.

 * demo_use_threadpool.py - app that displays a hello world and the wsgi
   environment using ISAPIThreadPoolHandler.

 * demo_serve_from_root.py - serve an app from IIS root that displays a hello world 
   and the wsgi environment using ISAPISimpleHandler.
 
 * echo.py - the test app from wsgi webkit. Used for isapi_wsgi unit tests.

 * multiple_apps.py - show how to support multiple wsgi apps from one isapi extension.

Also it is worthwhile reading the docs that come with the win32 isapi extension.

== Debugging ==

A simple trace function is provided that will allow viewing of print statements
using win32traceutil if the isapi_wsgi traceon global is set to 1.

== Caveats ==

If you make a change to your python code and things do not seem to work, try
restarting IIS. Starting and stopping the website within MMC is not enough.
I recommend the command line iisreset to stop and start IIS. This will clear
the environment and cleanly reload any changes to your code.

The extension dll must be run from a local drive. There may be issues if you
run from a mapped drive.

== To Do ==

Better documentation

Some unit tests

== Credits ==

Chris Lambacher for patches that removed limitations of my initial efforts.

Jason Coombs for improved virtual directory support and initial Python 3k support.

Sune Foldager & Dimitri Janczak for HTTPS environment variable patches.

Peter Hunt for initial code review and support.

Mark Hammond for the win32 extensions which are doing all the hard work, and his detailed
expanations on mailing list and coding help.

Phillip J. Eby for wsgiref which kept my implementation honest.

My wife and son for letting me spend some of their quality time working on this project.

