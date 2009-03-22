"""
$Id: isapi_wsgi.py 7 2005-02-08 02:40:30Z Mark $

This is a beta ISAPI extension for queued wsgi handler.

Dependecies:
    - python 2.2+
    - win32 extensions
    - wsgiref library from http://cvs.eby-sarna.com/wsgiref/

Based on isapi/test/extension_simple.py, PEP 333 etc

TODO:
    - sendfile
"""
__author__ = "Mark Rees <mark.john.rees@gmail.com>"
__version__ = "$Rev: 7 $ $LastChangedDate: 2005-02-08 13:40:30 +1100 (Tue, 08Feb 2005) $"
__url__ = "isapi-wsgi.python-hosting.com"
__description__ = "ISAPI WSGI SimpleHandler"
__license__ = "MIT"
from isapi import isapicon
from isapi.simple import SimpleExtension
from wsgiref.handlers import BaseHandler
import sys, os, stat, string
import threading
try: from cStringIO import StringIO
except ImportError: from StringIO import StringIO

if hasattr(sys, "isapidllhandle"):
    import win32traceutil

traceon = 0
def trace(*msgs):
    """Write trace message(s) so win32traceutil can display them"""
    if not traceon: return
    for msg in msgs:
        print msg

def fixPathinfo(scriptname, pathinfo):
    """Fix IIS PATH_NAME bug."""

    if string.find(pathinfo, scriptname) == 0:
        pathinfo = pathinfo[len(scriptname):]                
    
    return pathinfo

def fixScriptname(scriptname):
    '''Fix scriptname as described below.
    IIS evaluates SCRIPT_NAME as the path between scheme://host:port and
    the query string. For this wsgi implementation it is assumed that the
    SCRIPT_NAME should the IIS virtual directory and the app name.
    For example: /isapi_wsgi/demo
    '''
    if scriptname[-1] == "/":
        scriptname = scriptname[:-1]
    scriptname = "/".join(scriptname.split("/",3)[0:3])

    return scriptname

import win32event, win32file, winerror, win32con

class ISAPIInputWrapper:
    # Based on ModPythonInputWrapper in mp_wsgi_handler.py
    def __init__(self, ecb):
        self._in = StringIO()
        self._ecb = ecb
        if self._ecb.AvailableBytes > 0:
            data = self._ecb.AvailableData
            # Check if more data from client than what is in ecb.AvailableData
            excess = self._ecb.TotalBytes - self._ecb.AvailableBytes
            if excess > 0:
                extra = self._ecb.ReadClient(excess)
                data = data + extra
            self._in.write(data)
        # rewind to start
        self._in.seek(0)

    def next(self):
        return self._in.next()

    def read(self, size=-1):
        return self._in.read(size)
    
    def readline(self):
        return self._in.readline()
    
    def readlines(self, hint=-1):
        return self._in.readlines()

    def reset(self):
        self._in.reset()
    
    def seek(self, *args, **kwargs):
        self._in.seek(*args, **kwargs)
    
    def tell(self):
        return self._in.tell()

    def __iter__(self):
        return iter(self._in.readlines())

class ISAPIOutputWrapper:
    def __init__(self, ecb):
        self.ecb = ecb
    def write(self, msg):
        self.ecb.WriteClient(msg)
    def flush(self):
        pass

class ISAPIErrorWrapper:
    def write(self, msg):
        trace(msg)
    def flush(self):
        pass

# The ISAPI extension - handles requests in our virtual dir, and sends the
# response to the client.
class ISAPISimpleHandler(SimpleExtension, BaseHandler):
    '''Python Simple WSGI ISAPI Extension'''
    def __init__(self, **apps):
        trace("ISAPISimpleHandler.__init__")
        self.apps = apps
        self.ecb = None
        self.stdin = None
        self.stdout = None
        self.stderr = ISAPIErrorWrapper()
        self.base_env = []
        self.wsgi_multithread = False
        self.wsgi_multiprocess = False
        self.lock = threading.Lock()

    def HttpExtensionProc(self, ecb):
        trace("Enter HttpExtensionProc")
        self.lock.acquire() 
        self.ecb = ecb
        self.stdin = ISAPIInputWrapper(self.ecb)
        self.stdout = ISAPIOutputWrapper(self.ecb)
        self.headers = None
        self.headers_sent = False
        url = ecb.GetServerVariable("URL")
        if url[-1] == "/":
            url = url[:-1]
        sn = fixScriptname(ecb.GetServerVariable('SCRIPT_NAME'))
        wsgi_appname = sn.split("/")[-1]
        application = self.apps.get(wsgi_appname, None)
        try:
            if application is not None:
                self.run(application)        
            else:
                self.run(isapi_error)        
        except ExtensionError:
            # error normally happens when client disconnects before 
            # extension i/o completed
            pass
        except:
            # ToDo:Other exceptions should generate a nice page
            pass
        self.ecb.close()
        self.lock.release()
        trace("Exit HttpExtensionProc")
        return isapicon.HSE_STATUS_SUCCESS

    def TerminateExtension(self, status):
        trace("TerminateExtension")
    
    def send_preamble(self):
        """Since ISAPI sends preamble itself, do nothing"""
        trace("send_preamble")
    
    def send_headers(self):
        """Transmit headers to the client, via self._write()"""
        trace("send_headers", str(self.headers))
        self.cleanup_headers()
        self.headers_sent = True
        if not self.origin_server or self.client_is_modern():
            trace("SendResponseHeaders")
            self.ecb.SendResponseHeaders(self.status, str(self.headers), False)
            
    def _write(self, data):
        trace("_write", data)
        self.ecb.WriteClient(data)

    def _flush(self):
        trace("_flush")

    def get_stdin(self):
        trace("get_stdin")
        return self.stdin

    def get_stderr(self):
        trace("get_stderr")
        return self.stderr

    def add_cgi_vars(self):
        trace("add_cgi_vars")
        # get standard windows os environment
        environ = dict(os.environ.items())
        # set standard CGI variables
        required_cgienv_vars = ['REQUEST_METHOD', 'SCRIPT_NAME',
                                'PATH_INFO', 'QUERY_STRING',
                                'CONTENT_TYPE', 'CONTENT_LENGTH',
                                'SERVER_NAME', 'SERVER_PORT',
                                'SERVER_PROTOCOL'
                                ]
        for cgivar in required_cgienv_vars:
            try:
                environ[cgivar] = self.ecb.GetServerVariable(cgivar)
            except:
                raise AssertionError("missing CGI environment variable %s" % cgivar)

        # Due to an IIS bug ISAPI returns incorrect PATH_INFO and SCRIPT_NAME 
        # variables. Both variables are the extension name and the rest of 
        # the path upto the ?
        # Code below corrects the variables.
        pathinfo = environ['PATH_INFO']
        scriptname = fixScriptname(environ['SCRIPT_NAME'])
        environ['SCRIPT_NAME'] = scriptname
        environ['PATH_INFO'] = fixPathinfo(scriptname, pathinfo)

        http_cgienv_vars = self.ecb.GetServerVariable('ALL_HTTP').split("\n")
        for cgivar in http_cgienv_vars:
            pair = cgivar.split(":",1)
            try:
                environ[pair[0]] = pair[1]
            except:
                # Handle last list which is not a pair
                pass
        
        # Other useful CGI variables
        try:
            environ['REMOTE_USER'] = self.ecb.GetServerVariable('REMOTE_USER')
        except:
            pass

        self.environ.update(environ)

def isapi_error(environ, start_response):
    '''Send a nice error page to the client'''
    status = '404 OK'
    start_response(status, [('Content-type', 'text/plain')])
    return ['Page not found']

#-----------------------------------------------------------------------------
def test(environ, start_response):
    '''Simple app as per PEP 333'''
    status = '200 OK'
    start_response(status, [('Content-type', 'text/plain')])
    return ['Hello world from isapi!']


# The entry points for the ISAPI extension.
def __ExtensionFactory__():
    return ISAPISimpleHandler(test = test)



# Our special command line customization.
# Pre-install hook for our virtual directory.
def PreInstallDirectory(params, options):
    # If the user used our special '--description' option,
    # then we override our default.
    if options.description:
        params.Description = options.description

# Post install hook for our entire script
def PostInstall(params, options):
    print "Extension installed"

# Handler for our custom 'status' argument.
def status_handler(options, log, arg):
    "Query the status of something"
    print "Everything seems to be fine!"

custom_arg_handlers = {"status": status_handler}

if __name__=='__main__':
    # If run from the command-line, install ourselves.
    from isapi.install import *
    params = ISAPIParameters(PostInstall = PostInstall)
    # Setup the virtual directories - this is a list of directories our
    # extension uses - in this case only 1.
    # Each extension has a "script map" - this is the mapping of ISAPI
    # extensions.
    sm = [
        ScriptMapParams(Extension="*", Flags=0)
    ]
    vd = VirtualDirParameters(Name="isapi-wsgi-test",
                              Description = "ISAPI-WSGI Test",
                              ScriptMaps = sm,
                              ScriptMapUpdate = "replace",
                              # specify the pre-install hook.
                              PreInstall = PreInstallDirectory
                              )
    params.VirtualDirs = [vd]
    # Setup our custom option parser.
    from optparse import OptionParser
    parser = OptionParser('') # black usage, so isapi sets it.
    parser.add_option("", "--description",
                      action="store",
                      help="custom description to use for the virtual directory")
    
    HandleCommandLine(params, opt_parser=parser, 
                              custom_arg_handlers = custom_arg_handlers)