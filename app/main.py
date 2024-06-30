import asyncio
from urllib.parse import unquote
import argparse
import os
import gzip
import binascii


class HTTPServer:
    def __init__(self, host="localhost", port=4221):
        self.host = host
        self.port = port
        self.server = None
        self.routes = {
            "/": self.handle_root,
            "/echo": self.handle_echo,
            "/user-agent": self.handle_user_agent,
            "/files": self.handle_file
        }

    async def start_server(self):
        self.server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )
        addrs = ', '.join(str(sock.getsockname()) for sock in self.server.sockets)
        print(f'serving on {addrs}')

        async with self.server:
            await self.server.serve_forever()

    async def handle_connection(self, reader, writer):
        while True:
            request = await reader.read(1024)
            if not request:
                print("Close the connection")
                writer.close()
                await writer.wait_closed()
                return
            
            request = HTTPRequest.from_raw_response(request)
            
            target_path = request.target.split("?")[0].strip("/").split('/')[0]
            target_path = f"/{target_path}"
            handler = self.routes.get(target_path, self.handle_dynamic_route)
            await handler(writer, request)
            
    async def handle_root(self, writer, request):
        headers = {"Content-Type": "text/plain", "Content-Length": "2"}
        headers, _ = self.check_for_encoding(request, headers)
        return await self.send_response(writer, HTTPResponse(200, headers, "OK"))
    
    async def handle_echo(self, writer, request):
        echoed_string = request.target.split("/echo/", 1)[-1]
        echoed_string = unquote(echoed_string)
        headers = {
            "Content-Type": "text/plain",
            "Content-Length": str(len(echoed_string)),
        }
        headers, encoded_response = self.check_for_encoding(request, headers, echoed_string)
        await self.send_response(writer, HTTPResponse(200, headers, encoded_response))

    async def handle_dynamic_route(self, writer, request):
        if request.target.startswith("/echo/"):
            await self.handle_echo(writer, request)
        else:
            await self.handle_404(writer)
    
    async def handle_404(self, writer):
        headers = {"Content-Type": "text/plain", "Content-Length": "13"}
        await self.send_response(writer, HTTPResponse(404, headers, "404 Not Found"))

    async def handle_user_agent(self, writer, request):
        user_agent = request.header.get('User-Agent', 'Unknown')
        headers = {
            "Content-Type": "text/plain",
            "Content-Length": str(len(user_agent)),
        }
        headers, _ = self.check_for_encoding(request, headers)
        await self.send_response(writer, HTTPResponse(200, headers, user_agent))

    async def handle_file(self, writer, request):
        args = parse_arguments()
        file_name = request.target.split("/files/", 1)[-1]
        file_name = unquote(file_name)
        file_path = os.path.join(args.directory, file_name)

        if request.method == "POST":
            with open(file_path, "w+") as file:
                file.write(request.body)
            await self.send_response(writer, HTTPResponse(201, headers=None, message=""))

        elif os.path.isfile(file_path):
            with open(file_path, 'r') as file:
                file_content = file.read()
            file_size = os.path.getsize(file_path)
            headers = {
                "Content-Type": "application/octet-stream",
                "Content-Length": str(file_size),
            }
            headers, _ = self.check_for_encoding(request, headers)
            await self.send_response(writer, HTTPResponse(200, headers, file_content))
        else:
            await self.handle_404(writer)

    def check_for_encoding(self, request, headers, data_to_encode = None):
        encoding = request.header.get("Accept-Encoding", None)
        if encoding:
            encoding_methods = [method.strip() for method in encoding.split(",")]
            for method in encoding_methods:
                if method in self.compression_methods().keys():
                    headers["Content-Encoding"] = method
                    compression_function = self.compression_methods().get(method)
                    if data_to_encode:
                        data_to_encode = compression_function(data_to_encode)
                        print(data_to_encode)
                        headers["Content-Length"] = str(len(data_to_encode))
                    break
        return headers, data_to_encode

    async def send_response(self, writer, response):
        raw_response = response.to_raw_response()
        writer.write(raw_response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    def compression_methods(self):
        return {"gzip": self.gzip_compression}

    def gzip_compression(self, s):
        # Compress the bytes
        compressed_data = gzip.compress(s.encode("utf-8"))
        return compressed_data
    

class HTTPResponse:
    
    def __init__(self, status, headers = None, message=None):
        self.status_code = status
        self.headers = headers
        self.message = message

    def to_raw_response(self):
        response_line = f"HTTP/1.1 {self.status_code} {self.get_reason_phrase()}\r\n".encode('utf-8')
        if self.status_code == 201:
            return response_line + b"\r\n"
        
        if self.headers:
            headers = b"".join(
                [f"{key}: {value}\r\n".encode('utf-8') for key, value in self.headers.items()]
            )
        if isinstance(self.message, bytes):
            body = self.message  # Already a byte string if gzip-compressed
        else:
            body = self.message.encode('utf-8') if self.message else b""
        return response_line + headers + b"\r\n" + body
        
    def get_reason_phrase(self):
        phrases = {
            200: "OK",
            201: "Created",
            404: "Not Found",
        }
        return phrases.get(self.status_code, "Not Found")

            
class HTTPRequest:

    def __init__(self, method, target, version, header, body) -> None:
        self.method = method
        self.target = target
        self.version = version
        self.header = header
        self.body = body

    @classmethod
    def from_raw_response(cls, raw_request: bytes):
        decoded_response = raw_request.decode('utf-8')
        request_lines = decoded_response.split('\r\n')
        method, target, version = request_lines[0].split()
        headers = {}
        body_start_idx = 1
        for i, line in enumerate(request_lines[1:]):
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
            if line == "":
                body_start_idx = i+1

        body = "".join(request_lines[body_start_idx:])
        print(f"Request splitted: {request_lines}")
        return cls(method, target, version, headers, body)


def parse_arguments():
    parser = argparse.ArgumentParser(description="HTTP server")
    parser.add_argument('--directory', help="File directory")
    
    args = parser.parse_args()

    try:
        return args
    except Exception as e:
       raise ValueError("Invalid flag, please use --directory.")



if __name__ == "__main__":
    server = HTTPServer()
    asyncio.run(server.start_server())
