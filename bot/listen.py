import socket
import threading
import logging


def send_message(client, message):
    """Send message to client and close the connection."""
    client.send("HTTP/1.1 200 OK\r\n\r\n{}".format(message).encode("utf-8"))
    client.close()
    

def not_found(client):
    try:
        client.send('HTTP/1.1 404 Not Found\r\n\r\n'.encode('utf-8'))
        client.shutdown(socket.SHUT_RDWR)
        client.close()
    except:
        pass
    
 
def redirect(client):
    client.send('HTTP/1.1 303 See Other\r\nLocation: https://www.reddit.com\r\n\r\n'.encode('utf-8'))
    client.shutdown(socket.SHUT_RDWR)
    client.close()


def client_handler(client, queue):
    client.settimeout(1)
    try:
        data = client.recv(1024).decode('utf-8')
    except Exception as e:
        not_found(client)
        return 1
    
    try:
        param_tokens = data.split(' ', 2)[1].split('?')[1].split('&')
    except:
        not_found(client)
        return 1
    
    try:    
        params = {
            key: value
            for (key, value) in [token.split('=') for token in param_tokens]
        }
    except:
        not_found(client)
        return 1
        
    if "error" in params:
        send_message(client, params["error"])
        return 1
    
    try:
        params['state'] = int(params['state'])
    except Exception:
        not_found(client)
        return 1
    
    queue.put(params)
    
    try:
        redirect(client)
    except:
        return 1
        
    return 0

    
def listen(host, port, queue):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(4)

    while True:
        try:
            (client, addr) = server.accept()
            ct = threading.Thread(target=client_handler, args=(client, queue))
            ct.run()
        except KeyboardInterrupt:
            break
