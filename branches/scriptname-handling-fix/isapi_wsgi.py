"""
$Id: isapi_wsgi.py 7 2005-02-08 02:40:30Z Mark $

This is a beta ISAPI extension for a wsgi with 2 handlers classes.

    - ISAPISimpleHandler which creates a new IsapiWsgiHandler object for
      each request.
    - ISAPIThreadPoolHandler where the wsgi requests are run on worker threads
      from the thread pool.

Dependecies:
    - python 2.2+
    - win32 extensions
    - wsgiref library from http://cvs.eby-sarna.com/wsgiref/

Based on isapi/test/extension_simple.py, PEP 333 etc

"""
__author__ = "Mark Rees <mark.john.rees@gmail.com>"
__release__ = "0.3"
__version__ = "$Rev: 7 $ $LastChangedDate: 2005-02-08 13:40:30 +1100 (Tue, 08Feb 2005) $"
__url__ = "http://isapi-wsgi.googlecode.com"
__description__ = "ISAPI WSGI Handler"
__license__ = "MIT"

#this is first so that we can see import errors
import sys
if hasattr(sys, "isapidllhandle"):
    import win32traceutil

import re
from isapi import isapicon, ExtensionError
from isapi.simple import SimpleExtension
from isapi.threaded_extension import ThreadPoolExtension
from wsgiref.handlers import BaseHandler
import sys, os, stat, string
try: from cStringIO import StringIO
except ImportError: from StringIO import StringIO


traceon = 0
def trace(*msgs):
    """Write trace message(s) so win32traceutil can display them"""
    if not traceon: return
    for msg in msgs:
        print msg

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

def NullEnvironmentAdapter(environ):
	pass

class ScriptDepthEnvironmentAdapter(object):
    """
    Adapt the environment variables (in particular the SCRIPT_NAME
    and PATH_INFO vars) to correct for ISAPI behavior and deployment
    choices.
    
    >>> sample_env = dict(PATH_INFO='/foo/bar/baz', SCRIPT_NAME='/foo/bar/baz')
    >>> depth_2_env = sample_env.copy()
    >>> ScriptDepthEnvironmentAdapter()(depth_2_env)
    >>> depth_2_env['SCRIPT_NAME'], depth_2_env['PATH_INFO']
    ('/foo/bar', '/baz')
    >>> depth_1_env = sample_env.copy()
    >>> ScriptDepthEnvironmentAdapter(1)(depth_1_env)
    >>> depth_1_env['SCRIPT_NAME'], depth_1_env['PATH_INFO']
    ('/foo', '/bar/baz')
    """
    
    def __init__(self, script_depth=2):
        self.script_depth = script_depth
    
    def __call__(self, environ):
        """
        Due to an IIS bug, ISAPI returns incorrect PATH_INFO and SCRIPT_NAME 
        variables. Both variables include the full path up to the query string.
        This method is a workaround for that issue.
        
        This method assumes the first two segments of the path are part of the
        script and the rest is part of the path.
        
        Set the property 'script_depth' on this object to another number to
        specify a different depth.
        """
        path_info = environ['PATH_INFO']
        script_name = environ['SCRIPT_NAME']

        # first, we make the assumption that pathinfo and scriptname are the same.
        # Test that assumption.
        assert path_info == script_name, "Unexpected values for PATH_INFO/SCRIPT_NAME"

        # user_script_depth describes the number of names in the path; for compatibilty,
        #  default to 2.
        # e.g. /extension_dir/app -> script_depth==2
        #      /app               -> script_depth == 1
        #      /                  -> script_depth==0
        user_script_depth = getattr(self, 'script_depth')
        paths = path_info.split('/')
        split_index = user_script_depth + 1
        script_name = '/'.join(paths[:split_index])
        # path should always begin with a slash
        path_info = '/'.join([''] + paths[split_index:])
        
        environ['SCRIPT_NAME'] = script_name
        environ['PATH_INFO'] = path_info

class RegexEnvironmentAdapter(object):
    """
    Use a regex pattern to determine the script name
    
    >>> sample_env = dict(PATH_INFO='/foo/bar/baz', SCRIPT_NAME='/foo/bar/baz')
    >>> regex_env = sample_env.copy()
    >>> RegexEnvironmentAdapter('.*?bar')(regex_env)
    >>> regex_env['SCRIPT_NAME'], regex_env['PATH_INFO']
    ('/foo/bar', '/baz')
    >>> regex_env['SCRIPT_NAME'] = regex_env['PATH_INFO'] = '/anything_goes_here/and%20here/bar/baz'
    >>> RegexEnvironmentAdapter('.*?bar')(regex_env)
    >>> regex_env['SCRIPT_NAME'], regex_env['PATH_INFO']
    ('/anything_goes_here/and%20here/bar', '/baz')
    """
    def __init__(self, script_pattern):
        self.script_pattern = script_pattern
    
    def __call__(self, environ):
        match = re.match(self.script_pattern, environ['SCRIPT_NAME'])
        if not match:
            return # or raise an error?
        environ['SCRIPT_NAME'], environ['PATH_INFO'] = match.group(0), environ['SCRIPT_NAME'][match.end():]

class SubappEnvironmentAdapter(RegexEnvironmentAdapter):
    def __init__(self, app_names):
        app_names_pattern = '|'.join(app_names)
        pattern = '/[^/]+/(%s)' % app_names_pattern
        RegexEnvironmentAdapter.__init__(self, pattern)

class IsapiWsgiHandler(BaseHandler):
    """
    Handler
    """
    
    def __init__(self, ecb):
        self.ecb = ecb
        self.stdin = ISAPIInputWrapper(self.ecb)
        self.stdout = ISAPIOutputWrapper(self.ecb)
        self.stderr = sys.stderr #this will go to the win32traceutil
        self.headers = None
        self.headers_sent = False
        self.wsgi_multithread = False
        self.wsgi_multiprocess = False
        self.base_env = []

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

        self.environment_adapter(environ)

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

class ISAPIHandler(object):
    """Handler"""
    
    """
    environment_adapter should be a callable that accepts the environment
    and mutates it as appropriate.
    """
    environment_adapter = ScriptDepthEnvironmentAdapter()
    
    def _run_app(self, ecb):
        application = self._select_application(ecb)

        handler = IsapiWsgiHandler(ecb)
        handler.environment_adapter = self.environment_adapter
        trace("Handler")
        try:
            if application is not None:
                handler.run(application)        
            else:
                handler.run(isapi_error)        
        except ExtensionError:
            # error normally happens when client disconnects before 
            # extension i/o completed
            pass
        except:
            # ToDo:Other exceptions should generate a nice page
            trace("Caught App Exception")
            pass

    def _select_application(self, ecb):
        "Determine the application based on the SCRIPT_INFO/PATH_INFO"
        partial_env = dict([(param, ecb.GetServerVariable(param)) for param in ('SCRIPT_NAME', 'PATH_INFO')])
        self.environment_adapter(partial_env)
        sn = partial_env['SCRIPT_NAME']
        wsgi_appname = sn.split("/")[-1]
        application = self.apps.get(wsgi_appname, self.rootapp)
        return application

    
# The ISAPI extension - handles requests in our virtual dir, and sends the
# response to the client.
class ISAPISimpleHandler(SimpleExtension, ISAPIHandler):
    '''Python Simple WSGI ISAPI Extension'''
    def __init__(self, rootapp=None, **apps):
        trace("ISAPISimpleHandler.__init__")
        self.rootapp = rootapp
        self.apps = apps

        SimpleExtension.__init__(self)

    def HttpExtensionProc(self, ecb):
        trace("Enter HttpExtensionProc")

        self._run_app(ecb)
        ecb.close()
        
        trace("Exit HttpExtensionProc")
        return isapicon.HSE_STATUS_SUCCESS

    def TerminateExtension(self, status):
        trace("TerminateExtension")

class ISAPIThreadPoolHandler(ThreadPoolExtension, ISAPIHandler):
    '''Python Thread Pool WSGI ISAPI Extension'''
    def __init__(self, rootapp=None, **apps):
        trace("ISAPIThreadPoolHandler.__init__")
        self.rootapp = rootapp
        self.apps = apps

        ThreadPoolExtension.__init__(self)

    def Dispatch(self, ecb):
        trace("Enter Dispatch")
        self._run_app(ecb)
        ecb.DoneWithSession()
        trace("Exit Dispatch")

    

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
    return ISAPISimpleHandler(test)



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
