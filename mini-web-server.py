import http.server
import subprocess
from pathlib import Path
from typing import Union


class ServerException(Exception):
    pass


class BaseCase:
    @staticmethod
    def handle_file(request_handler, full_path_to_file: Path):
        try:
            with open(full_path_to_file, 'r') as f:
                content = f.read()
            request_handler.send_content(content)
        except IOError as msg:
            msg = f"'{full_path_to_file}' cannot be read: {msg}"
            request_handler.handle_error(msg)

    @staticmethod
    def index_path(request_handler):
        return request_handler.full_path / 'index.html'

    def test(self, request_handler):
        raise NotImplementedError

    def act(self, request_handler):
        raise NotImplementedError


class CaseNoFile(BaseCase):
    """
    File or directory does not exist.
    """

    def test(self, request_handler):
        return not request_handler.full_path.exists()

    def act(self, request_handler):
        raise ServerException("f'{request_handler.path}' not found")


class CaseExistingFile(BaseCase):
    """
    File exists.
    """

    def test(self, request_handler):
        return request_handler.full_path.is_file()

    def act(self, request_handler):
        self.handle_file(request_handler=request_handler, full_path_to_file=request_handler.full_path)


class CaseAlwaysFail(BaseCase):
    """
    Base case if nothing else worked.
    """

    def test(self, request_handler):
        return True

    def act(self, request_handler):
        raise ServerException(f"Unknown object '{request_handler.path}'")


class CaseDirectoryIndexFile(BaseCase):
    """
    Serve index.html page if exists in directory.
    """

    def test(self, request_handler):
        return request_handler.full_path.is_dir() and self.index_path(request_handler).is_file()

    def act(self, request_handler):
        self.handle_file(request_handler=request_handler, full_path_to_file=self.index_path(request_handler))


class CaseDirectoryNoIndexFile(BaseCase):
    """
    List contents of a directory.
    """

    def test(self, request_handler):
        return request_handler.full_path.is_dir() and not self.index_path(request_handler).is_file()

    def act(self, request_handler):
        request_handler.list_directory_contents(full_path_to_directory=request_handler.full_path)


class CaseCGIFile(BaseCase):
    """
    Run python server side and return the results.
    """

    def test(self, request_handler):
        return request_handler.full_path.is_file and str(request_handler.full_path).endswith('.py')

    def act(self, request_handler):
        request_handler.run_cgi_script(path_to_executable=request_handler.full_path)


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
                    _case.act(self)
                    break

        # Handle errors.
        except Exception as msg:
            self.handle_error(msg)

    def run_cgi_script(self, path_to_executable: Path) -> None:
        cmd = "python " + str(path_to_executable)
        result = subprocess.run(cmd.split(' '), stdout=subprocess.PIPE)
        self.send_content(str(result.stdout))

    def list_directory_contents(self, full_path_to_directory: Path) -> None:
        try:
            contents = full_path_to_directory.glob('**/*')
            bullets = ['<li>{0}</li>'.format(file) for file in contents if not str(file).startswith('.')]
            page = self.directory_listing_page.format('\n'.join(bullets))
            self.send_content(page)
        except OSError as msg:
            msg = f"'{self.path}' cannot be listed: {msg}"
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
