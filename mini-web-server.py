import http.server
import subprocess
from pathlib import Path
from typing import Union


class ServerException(Exception):
    pass


class BaseCase:
    """
    Parent for case handlers.
    """

    @staticmethod
    def handle_file(handler, full_path: Path):
        try:
            with open(full_path, 'r') as reader:
                content = reader.read()
            handler.send_content(content)
        except IOError as msg:
            msg = "'{0}' cannot be read: {1}".format(full_path, msg)
            handler.handle_error(msg)

    @staticmethod
    def index_path(handler):
        return handler.full_path / 'index.html'

    def test(self, handler):
        raise NotImplementedError

    def act(self, handler):
        raise NotImplementedError


class CaseNoFile(BaseCase):
    """
    File or directory does not exist.
    """

    def test(self, handler):
        return not handler.full_path.exists()

    def act(self, handler):
        raise ServerException("'{0}' not found".format(handler.path))


class CaseExistingFile(BaseCase):
    """
    File exists.
    """

    def test(self, handler):
        return handler.full_path.is_file()

    def act(self, handler):
        self.handle_file(handler, handler.full_path)


class CaseAlwaysFail(BaseCase):
    """
    Base case if nothing else worked.
    """

    def test(self, handler):
        return True

    def act(self, handler):
        raise ServerException("Unknown object '{0}'".format(handler.path))


class CaseDirectoryIndexFile(BaseCase):
    """
    Serve index.html page for a directory.
    """

    def test(self, handler):
        return handler.full_path.is_dir() and self.index_path(handler).is_file()

    def act(self, handler):
        self.handle_file(handler, self.index_path(handler))


class CaseDirectoryNoIndexFile(BaseCase):
    """
    Serve index.html page for a directory.
    """

    def test(self, handler):
        return handler.full_path.is_dir() and not self.index_path(handler).is_file()

    def act(self, handler):
        handler.list_dir(full_path=handler.full_path)


class CaseCGIFile(BaseCase):
    """
    Something runnable.
    """

    def test(self, handler):
        return handler.full_path.is_file and str(handler.full_path).endswith('.py')

    def act(self, handler):
        handler.run_cgi(handler.full_path)


class RequestHandler(http.server.BaseHTTPRequestHandler):
    """
    Handle HTTP requests by returning a fixed 'page'.

    """

    cases = [
        CaseCGIFile,
        CaseNoFile,
        CaseExistingFile,
        CaseDirectoryIndexFile,
        CaseDirectoryNoIndexFile,
        CaseAlwaysFail
    ]

    error_page = """
        <html>
        <body>
        <h1>Error accessing {path}</h1>
        <p>{msg}</p>
        </body>
        </html>
        """

    # How to display a directory listing.
    directory_listing_page = """
        <html>
        <body>
        <ul>
        {0}
        </ul>
        </body>
        </html>
        """

    # Handle a GET request.
    def do_GET(self) -> None:
        try:
            # Figure out what exactly is being requested.
            self.full_path = Path.cwd() / self.path[1:]

            # Figure out how to handle it.
            for case in self.cases:
                _case = case()
                if _case.test(self):
                    print(_case.__class__)
                    _case.act(self)
                    break

        # Handle errors.
        except Exception as msg:
            self.handle_error(msg)

    def run_cgi(self, full_path: Path) -> None:
        cmd = "python " + str(full_path)
        result = subprocess.run(cmd.split(' '), stdout=subprocess.PIPE)
        self.send_content(str(result.stdout))

    def list_dir(self, full_path: Path) -> None:
        try:
            entries = full_path.glob('**/*')
            bullets = ['<li>{0}</li>'.format(e) for e in entries if not str(e).startswith('.')]
            page = self.directory_listing_page.format('\n'.join(bullets))
            self.send_content(page)
        except OSError as msg:
            msg = "'{0}' cannot be listed: {1}".format(self.path, msg)
            self.handle_error(msg)

    # Handle unknown objects.
    def handle_error(self, msg: Union[str, Exception]) -> None:
        content = self.error_page.format(path=self.path, msg=msg)
        self.send_content(content, 404)

    # Send actual content.
    def send_content(self, content: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(str.encode(content))


if __name__ == '__main__':
    serverAddress = ('', 8080)
    server = http.server.HTTPServer(serverAddress, RequestHandler)
    server.serve_forever()
