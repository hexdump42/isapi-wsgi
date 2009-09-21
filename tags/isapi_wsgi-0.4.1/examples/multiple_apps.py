__doc__ = '''
An example of how isapi_wsgi can be configured to run multiple apps from
a single extension. Also set one of the apps to serve from root.

 To launch this application from a web browser use a url similar to:

  http://localhost/isapi-wsgi-multiple-apps/simple_app
  http://localhost/isapi-wsgi-multiple-apps/demo
  http://localhost/isapi-wsgi-multiple-apps/echo

  http://localhost/isapi-wsgi-multiple-apps/  will serve the echo app
'''
import isapi_wsgi

# The entry points for the ISAPI extension.
def __ExtensionFactory__():
    # TODO: The list should be loaded from a config file
    resources = [
        {"name" : "echo", "module" : "echo", "object" : "application"},
        {"name" : "simple_app", "module" : "simple", "object" : "simple_app"},
        {"name" : "demo", "module" : "demo", "object" : "demo_app"},
    ]
    apps = {}
    for res in resources:
        try:
            import_hook = __import__(res['module'])
            import_hook = getattr(import_hook,res['object'])
            apps[res['name']] = import_hook
        except ImportError:
            raise AssertionError("Problems importing module %s." % res['module'])

    return isapi_wsgi.ISAPISimpleHandler(rootapp=apps['echo'], **apps)



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
    vd = VirtualDirParameters(Name="isapi-wsgi-multiple-apps",
                              Description = "ISAPI-WSGI Multiple Apps Demo",
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
