import socket
import threading

class Client:
    def __init__(self, host='127.0.0.1', port=12345):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((host, port))

    def send_command(self, command):
        self.client.sendall(command.encode() + b'\n')

    def receive_message(self):
        while True:
            msg = self.client.recv(1024).decode().strip()
            if msg:
                print(msg)

    def start(self):
        threading.Thread(target=self.receive_message, daemon=True).start()
        while True:
            command = input()
            self.send_command(command)
            if command.startswith("/exit"):
                break

if __name__ == "__main__":
    client = Client()
    client.start()