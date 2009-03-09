"""
$Id$

This is a ISAPI extension for a wsgi with 2 handlers classes.

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
__release__ = "0.4"
__version__ = "$Rev$ $LastChangedDate$"
__url__ = "http://isapi-wsgi.googlecode.com"
__description__ = "ISAPI WSGI Handler"
__license__ = "MIT"

#this is first so that we can see import errors
import sys
if hasattr(sys, "isapidllhandle"):
    import win32traceutil

from isapi import isapicon, ExtensionError
from isapi.simple import SimpleExtension
from isapi.threaded_extension import ThreadPoolExtension
from wsgiref.handlers import BaseHandler
from wsgiref.util import shift_path_info
import sys, os, stat, string
try: from cStringIO import StringIO
except ImportError: from StringIO import StringIO


traceon = 0
def trace(*msgs):
    """Write trace message(s) so win32traceutil can display them"""
    if not traceon: return
    for msg in msgs:
        print(msg)

class ECBDictAdapter(object):
    """
    Adapt ECB to a read-only dictionary interface
    
    >>> from fakeecb import FakeECB
    >>> ecb = FakeECB()
    >>> ecb_dict = ECBDictAdapter(ecb)
    >>> ecb_dict['SCRIPT_NAME']
    '/'
    >>> ecb_dict['PATH_INFO']
    '/'
    """
    def __init__(self, ecb):
        self.ecb = ecb
        if sys.version_info > (3,0):
            if ecb.Version >= 0x00060000:
                # we can handle UNICODE_* variables.
                self._get_variable = self._get_variable_py3k
            else:
                self._get_variable = self._get_variable_py3k_iis5
        else:
            self._get_variable = self._get_variable_py2k

    def __getitem__(self, key):
        try:
            return self._get_variable(key)
        except ExtensionError:
            raise KeyError, key

    # a few helpers specific to the IIS and python version.
    def _get_variable(self, key):
        raise RuntimeError("not reached: replaced at runtime in the ctor")

    def _get_variable_py3k_iis5(self, key):
        # IIS5 doesn't support UNICODE_* variable names...
        return self.ecb.GetServerVariable(key).decode('latin-1')

    def _get_variable_py3k(self, key):
        # IIS6 and later on py3k - ask IIS for the unicode version.
        return self.ecb.GetServerVariable('UNICODE_' + key)

    def _get_variable_py2k(self, key):
        # py2k - just use normal string objects.
        return self.ecb.GetServerVariable(key)

def path_references_application(path, apps):
    """
    Return true if the first element in the path matches any string
    in the apps list.
    
    >>> path_references_application('/foo/bar', ['foo','baz'])
    True
    
    """
    # assume separator is /
    nodes = filter(None, path.split('/'))
    return nodes and nodes[0] in apps

def interpretPathInfo(ecb_server_vars, app_names=[]):
    """
    Based on the a dictionary of ECB server variables and list of valid
    subapplication names, determine the correct PATH_INFO, SCRIPT_NAME,
    and IIS_EXTENSION_PATH.
    
    By valid, I mean SCRIPT_NAME + PATH_INFO is always the request path and
    SCRIPT_NAME is the path to the WSGi application and PATH_INFO is the path
    that the WSGI application expects to handle.
    
    In IIS, the path to the extension sometimes varies from the script name,
    particularly when the script map extenison is not '*'.  IIS_EXTENSION_PATH
    is set to the path that leads to the extension.
    
    Return these values as a dict.
    
    For the following doctests, I use a convention:
     vappname : the IIS application
     appname : the wsgi application (may be )
     subappX : a wsgi sub application (must always follow appname)
     proc : a method within the WSGI app (something that should appear in PATH_INFO)
    
    --------------------------
    First some common examples
    
    Following is an example case where the extension is installed at the root
     of the site, the requested
     URL is /proc
    >>> ecb_vars = dict(SCRIPT_NAME='/proc', PATH_INFO='/proc', APPL_MD_PATH='/LM/W3SVC/1/ROOT')
    >>> interpretPathInfo(ecb_vars) == dict(SCRIPT_NAME='', PATH_INFO='/proc', IIS_EXTENSION_PATH='')
    True

    An example where the extension is installed to a virtual directory below
     the root.
     URL is /vappname/proc
    >>> ecb_vars = dict(SCRIPT_NAME='/vappname/proc', PATH_INFO='/vappname/proc', APPL_MD_PATH='/LM/W3SVC/1/ROOT/vappname')
    >>> interpretPathInfo(ecb_vars) == dict(SCRIPT_NAME='/vappname', PATH_INFO='/proc', IIS_EXTENSION_PATH='/vappname')
    True
    
    An example where the extension is installed to a virtual directory below
     the root, and some subapps are present
    >>> subapps = ('subapp1', 'subapp2')
    
     URL is /vappname/proc
    >>> ecb_vars = dict(SCRIPT_NAME='/vappname/proc', PATH_INFO='/vappname/proc', APPL_MD_PATH='/LM/W3SVC/1/ROOT/vappname')
    >>> interpretPathInfo(ecb_vars, subapps) == dict(SCRIPT_NAME='/vappname', PATH_INFO='/proc', IIS_EXTENSION_PATH='/vappname')
    True
    
     URL is /vappname/subapp1/proc
    >>> ecb_vars = dict(SCRIPT_NAME='/vappname/subapp1/proc', PATH_INFO='/vappname/subapp1/proc', APPL_MD_PATH='/LM/W3SVC/1/ROOT/vappname')
    >>> interpretPathInfo(ecb_vars, subapps) == dict(SCRIPT_NAME='/vappname/subapp1', PATH_INFO='/proc', IIS_EXTENSION_PATH='/vappname', WSGI_SUBAPP='subapp1')
    True
    
    ------------------------------
    Now some less common scenarios
    
    An example where the extension is installed only to the .wsgi extension to
     a virtual directory below the root.
     URL is /vappname/any.wsgi/proc
    >>> ecb_vars = dict(SCRIPT_NAME='/vappname/any.wsgi', PATH_INFO='/vappname/any.wsgi/proc', APPL_MD_PATH='/LM/W3SVC/1/ROOT/vappname')
    >>> interpretPathInfo(ecb_vars) == dict(SCRIPT_NAME='/vappname/any.wsgi', PATH_INFO='/proc', IIS_EXTENSION_PATH='/vappname')
    True

    An example where the extension is installed only to the .wsgi extension at
     the root.
     URL is /any_path/any.wsgi/proc
    >>> ecb_vars = dict(SCRIPT_NAME='/any_path/any.wsgi', PATH_INFO='/any_path/any.wsgi/proc', APPL_MD_PATH='/LM/W3SVC/1/ROOT')
    >>> interpretPathInfo(ecb_vars) == dict(SCRIPT_NAME='/any_path/any.wsgi', PATH_INFO='/proc', IIS_EXTENSION_PATH='')
    True
    
    How about an extension installed at the root to the .wsgi extension with
     subapps
     URL is /any_path/any.wsgi/subapp1/proc/foo
    >>> ecb_vars = dict(SCRIPT_NAME='/any_path/any.wsgi', PATH_INFO='/any_path/any.wsgi/subapp1/proc/foo', APPL_MD_PATH='/LM/W3SVC/1/ROOT')
    >>> interpretPathInfo(ecb_vars, subapps) == dict(SCRIPT_NAME='/any_path/any.wsgi/subapp1', PATH_INFO='/proc/foo', IIS_EXTENSION_PATH='', WSGI_SUBAPP='subapp1')
    True
    
    How about an extension installed at the root to the .wsgi extension with
     subapps... this time default to the root app.
     URL is /any_path/any.wsgi/proc/foo
    >>> ecb_vars = dict(SCRIPT_NAME='/any_path/any.wsgi', PATH_INFO='/any_path/any.wsgi/proc/foo', APPL_MD_PATH='/LM/W3SVC/1/ROOT')
    >>> interpretPathInfo(ecb_vars, subapps) == dict(SCRIPT_NAME='/any_path/any.wsgi', PATH_INFO='/proc/foo', IIS_EXTENSION_PATH='')
    True
    
    """
    
    PATH_INFO = ecb_server_vars['PATH_INFO']
    SCRIPT_NAME = ecb_server_vars['SCRIPT_NAME']
    IIS_EXTENSION_PATH = getISAPIExtensionPath(ecb_server_vars)
    
    if SCRIPT_NAME == PATH_INFO:
        # since they're the same, we're in a * mapped extension; use
        # the application path
        SCRIPT_NAME = IIS_EXTENSION_PATH

    # remove the script name from the path info
    if SCRIPT_NAME and PATH_INFO.startswith(SCRIPT_NAME):
        _, PATH_INFO = PATH_INFO.split(SCRIPT_NAME, 1)

    result = dict(
        SCRIPT_NAME=SCRIPT_NAME,
        PATH_INFO=PATH_INFO,
        IIS_EXTENSION_PATH=IIS_EXTENSION_PATH,
        )
    
    # finally, adjust the result if the path info begins with a subapp
    if path_references_application(PATH_INFO, app_names):
        result.update(WSGI_SUBAPP = shift_path_info(result))

    return result

def getISAPIExtensionPath(ecb_server_vars):
    """Returns the path to our extension DLL.
    
    This will be blank ('') if installed at the root, or something like
    '/foo' or '/bar/foo' if 'foo' is the name of the virtual directory
    where this extension is installed.
    
    >>> getISAPIExtensionPath(dict(APPL_MD_PATH='/LM/W3SVC/1/ROOT/test'))
    '/test'
    
    >>> getISAPIExtensionPath(dict(APPL_MD_PATH='/LM/W3SVC/1/ROOT'))
    ''
    """
    # Only way I see how to do this is to fetch the location of our ISAPI 
    # extension in the metabase then assume that '/ROOT/' is the root!
    # It will be something like MD='/LM/W3SVC/1/ROOT/test'
    appl_md_path = ecb_server_vars["APPL_MD_PATH"]
    site, pos = appl_md_path.split("/ROOT", 1)
    return pos

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
    
    def readline(self, size=-1):
        return self._in.readline(size)
    
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

class IsapiWsgiHandler(BaseHandler):
    def __init__(self, ecb, path_info):
        self.ecb = ecb
        self.path_info = path_info
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
                                'SERVER_PROTOCOL', 'REMOTE_ADDR'
                                ]
        ecb_dict = ECBDictAdapter(self.ecb)
        for cgivar in required_cgienv_vars:
            try:
                environ[cgivar] = ecb_dict[cgivar]
            except KeyError:
                raise AssertionError("missing CGI environment variable %s" % cgivar)

        environ.update(self.path_info)

        http_cgienv_vars = ecb_dict['ALL_HTTP'].split("\n")
        for cgivar in http_cgienv_vars:
            pair = cgivar.split(":",1)
            try:
                environ[pair[0]] = pair[1]
            except:
                # Handle last list which is not a pair
                pass
        
        # Other useful CGI variables
        try:
            environ['REMOTE_USER'] = ecb_dict['REMOTE_USER']
        except KeyError:
            pass

        # and some custom ones.
        environ['isapi.ecb'] = self.ecb

        self.environ.update(environ)

def _run_app(rootapp, apps, ecb):
    ecb_dict = ECBDictAdapter(ecb)
    path_info = interpretPathInfo(ecb_dict, apps.keys())
    loc = path_info.get('WSGI_SUBAPP')
    application = apps.get(loc, rootapp)

    # we have to pass path_info because otherwise the handler can't determine
    #  what the correct path is (because it doesn't know whether it's a
    #  subapp or not)
    handler = IsapiWsgiHandler(ecb, path_info)
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

    
# The ISAPI extension - handles requests in our virtual dir, and sends the
# response to the client.
class ISAPISimpleHandler(SimpleExtension):
    '''Python Simple WSGI ISAPI Extension'''
    def __init__(self, rootapp=None, **apps):
        trace("ISAPISimpleHandler.__init__")
        self.rootapp = rootapp
        self.apps = apps

        SimpleExtension.__init__(self)

    def HttpExtensionProc(self, ecb):
        trace("Enter HttpExtensionProc")

        _run_app(self.rootapp, self.apps, ecb)
        ecb.close()
        
        trace("Exit HttpExtensionProc")
        return isapicon.HSE_STATUS_SUCCESS

    def TerminateExtension(self, status):
        trace("TerminateExtension")

class ISAPIThreadPoolHandler(ThreadPoolExtension):
    '''Python Thread Pool WSGI ISAPI Extension'''
    def __init__(self, rootapp=None, **apps):
        trace("ISAPIThreadPoolHandler.__init__")
        self.rootapp = rootapp
        self.apps = apps

        ThreadPoolExtension.__init__(self)

    def Dispatch(self, ecb):
        trace("Enter Dispatch")
        _run_app(self.rootapp, self.apps, ecb)
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
