from StringIO import StringIO

class FakeECB:
    def __init__(self):
        self._stdout = StringIO()
        self.AvailableBytes = 0
        self.vars = { 
                    "REQUEST_METHOD":"GET",
                    "SCRIPT_NAME":"/",
                    "PATH_INFO":"/",
                    "QUERY_STRING":"",
                    "CONTENT_TYPE":"",
                    "CONTENT_LENGTH":"0",
                    "SERVER_NAME":"localhost",
                    "SERVER_PORT":"80",
                    "SERVER_PROTOCOL":"HTTP/1.0",
                    "ALL_HTTP":""}



    def WriteClient(self, s):
        self._stdout.write(s)

    write = WriteClient

    def close(self):
        print str(id(self)) +" close()"

    def GetServerVariable(self, cgivar):
        return self.vars[cgivar]

    def SendResponseHeaders(self, status, headers, ka):
        self._stdout.write(status + "\r\n")
        self._stdout.write(headers)
        



