# The echo example from wsgi webkit.
#
# Executing this script (or any server config script) will install the extension
# into your web server and will create a "loader" DLL _echo.dll in the 
# current directory. As the server executes, the PyISAPI framework will load
# this module and create the Extension object.
# A Virtual Directory named "isapi-wsgi-echo" is setup. This dir has the ISAPI
# WSGI extension as the only application, mapped to file-extension '*'.  
# Therefore, isapi_wsgi extension handles *all* requests in this directory.
#
# To launch this application from a web browser use a url similar to:
#
#  http://localhost/isapi-wsgi-echo/echo
#

r"""\
WSGI application from webkit

Does things as requested.  Takes variables:

header.header-name=value, like
  header.location=http://yahoo.com

error=code, like
  error=301 (temporary redirect)
  error=assert (assertion error)

environ=true,
  display all the environmental variables, like
  key=str(value)\n

message=string
  display string
"""

import cgi

def application(environ, start_response):
    form = cgi.FieldStorage(fp=environ['wsgi.input'],
                            environ=environ,
                            keep_blank_values=True)
    headers = {}
    for key in form.keys():
        if key.startswith('header.'):
            headers[key[len('header.'):]] = form[key].value
            
    if form.getvalue('error') and form['error'].value != 'iter':
        if form['error'].value == 'assert':
            assert 0, "I am asserting zero!"
        '''raise httpexceptions.get_exception(int(form['error'].value))(
            headers=headers)
	'''

    if form.getvalue('environ'):
        write = start_response('200 OK', [('Content-type', 'text/plain')])
        items = environ.items()
        items.sort()
        return ['%s=%s\n' % (name, value)
                for name, value in items]

    if form.has_key('message'):
        write = start_response('200 OK', [('Content-type', 'text/plain')])
        write(form['message'].value)
        return []

    if form.getvalue('error') == 'iter':
        return BadIter()
        
    write = start_response('200 OK', [('Content-type', 'text/html')])
    return ['hello world!']

class BadIter(object):
    def __iter__(self):
        assert 0, "I am assert zero in the iterator!"

import isapi_wsgi
# The entry points for the ISAPI extension.
def __ExtensionFactory__():
    return isapi_wsgi.ISAPISimpleHandler(echo = application)

if __name__=='__main__':
    # If run from the command-line, install ourselves.
    from isapi.install import *
    params = ISAPIParameters()
    # Setup the virtual directories - this is a list of directories our
    # extension uses - in this case only 1.
    # Each extension has a "script map" - this is the mapping of ISAPI
    # extensions.
    sm = [
        ScriptMapParams(Extension="*", Flags=0)
    ]
    vd = VirtualDirParameters(Name="isapi-wsgi-echo",
                              Description = "ISAPI-WSGI Echo Test",
                              ScriptMaps = sm,
                              ScriptMapUpdate = "replace"
                              )
    params.VirtualDirs = [vd]
    HandleCommandLine(params)
