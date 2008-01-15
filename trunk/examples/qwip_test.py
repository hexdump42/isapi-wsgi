# Demo of running a quixote app using Titus Browns' QWIP under isapi-wsgi
#
# Executing this script (or any server config script) will install the extension
# into your web server and will create a "loader" DLL _qwip_test.dll in the 
# current directory. As the server executes, the PyISAPI framework will load
# this module and create the Extension object.
# A Virtual Directory named "isapi-wsgi-qwip-test" is setup. This dir has the ISAPI
# WSGI extension as the only application, mapped to file-extension '*'.  
# Therefore, isapi_wsgi extension handles *all* requests in this directory.
#
# Requires 
#  * Quixote 1.2 (http://www.mems-exchange.org/software/quixote/)
#  * QWIP (http://www.idyll.org/~t/www-tools/wsgi/)
#
# To launch this application from a web browser use a url similar to:
#
#  http://localhost/isapi-wsgi-qwip-test/
#

import isapi_wsgi
import qwip

# The entry points for the ISAPI extension.
def __ExtensionFactory__():
    return isapi_wsgi.ISAPISimpleHandler(qwip.QWIP('quixote.demo'))

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
    vd = VirtualDirParameters(Name="isapi-wsgi-qwip-test",
                              Description = "ISAPI-WSGI QWIP Test",
                              ScriptMaps = sm,
                              ScriptMapUpdate = "replace"
                              )
    params.VirtualDirs = [vd]
    HandleCommandLine(params)
