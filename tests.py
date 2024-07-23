import unittest
from server import Server
import socket
import threading
import time

class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server()
        threading.Thread(target=cls.server.start, daemon=True).start()
        time.sleep(1)  # Give server time to start

    def setUp(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(('127.0.0.1', 12345))

    def tearDown(self):
        self.client.close()

    def send_command(self, command):
        self.client.sendall(command.encode() + b'\n')
        response = self.client.recv(1024).decode().strip()
        return response

    def test_username(self):
        response = self.send_command("/username alice")
        self.assertEqual(response, "/username ok")

    def test_create_and_join_room(self):
        self.send_command("/username bob")
        response = self.send_command("/create #testroom")
        self.assertEqual(response, "/create ok")
        response = self.send_command("/join #testroom")
        self.assertEqual(response, "/join ok")

    def test_send_message(self):
        self.send_command("/username charlie")
        self.send_command("/join #welcome")
        response = self.send_command("/msg Hello everyone!")
        self.assertEqual(response, "/msg sent")

    def test_private_message(self):
        self.send_command("/username dave")
        self.send_command("/join #welcome")
        response = self.send_command("/pmsg charlie Hello, Charlie!")
        self.assertEqual(response, "/pmsg sent")

if __name__ == "__main__":
    unittest.main()
