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
        time.sleep(2)

    def setUp(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(('127.0.0.1', 12345))
        self.client.recv(1024)

    def tearDown(self):
        self.client.close()

    def send_command(self, command):
        self.client.sendall(command.encode() + b'\n')
        response = self.client.recv(1024).decode().strip()
        return response

    def test_username(self):
        response = self.send_command("/username test")
        self.assertEqual(response, "/username ok")

    def test_create_and_join_room(self):
        self.send_command("/username test2")
        response = self.send_command("/create #testroom")
        self.assertEqual(response, "/create ok")
        response = self.send_command("/join #testroom")
        self.assertEqual(response, "/join ok")   

    def test_msg(self):
        self.send_command("/username test3")
        self.send_command("/create #testroom")
        self.send_command("/join #testroom")
        response = self.send_command("/msg Hello from test3")
        self.assertEqual(response, "/msg sent")

    def test_msgs(self):
        self.send_command("/username test4")
        self.send_command("/join #welcome")
        self.send_command("/msg Hello from test4")
        time.sleep(1)
        response = self.send_command("/msgs")
        self.assertIn("Hello from test4", response)

if __name__ == "__main__":
    unittest.main()
