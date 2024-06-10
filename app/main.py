# Uncomment this to pass the first stage
import socket





def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    # Uncomment this to pass the first stage
    #
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    while True:
        connection, client_address = server_socket.accept() # wait for clienter
        print(f"connection from client address: {client_address}")
        request_data = connection.recv(1024)
        print("Received request data:")
        print(request_data.decode('utf-8'))
        print(request_data)
        response = parse_request(request_data)
        connection.sendall(response)
        connection.close()


def parse_request(request_data: bytes):
    decoded_response = request_data.decode('utf-8')
    request = decoded_response.split('\r\n')
    method, path, http_version = request[0].split()
    if path == "/":
        response = b"HTTP/1.1 200 OK\r\n\r\n"
    elif "echo" in path:
        request_body = path.split("/")[-1]
        response = generate_response(request_body, http_version)
    elif "user-agent" in path:
        request_body = request[2].split(' ')[-1]
        response = generate_response(request_body, http_version)
    else:
        response = b"HTTP/1.1 404 Not Found\r\n\r\n"
    return response


def generate_response(request_body: str, http_version):
    status_code = "200 OK\r\n"
    content_type = "Content-Type: text/plain\r\n"
    content_len = f'Content-Length: {len(request_body)}\r\n\r\n'
    response = f"{http_version} {status_code}{content_type}{content_len}{request_body}"
    response = response.encode('utf-8')
    return response
                




if __name__ == "__main__":
    main()
