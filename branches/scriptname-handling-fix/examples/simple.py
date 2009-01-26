# This simple WSGI app is called by the multiple_apps.py
def simple_app(environ, start_response):
    '''Simple app as per PEP 333'''
    status = '200 OK'
    start_response(status, [('Content-type', 'text/plain')])
    return ['Hello world from isapi!']

