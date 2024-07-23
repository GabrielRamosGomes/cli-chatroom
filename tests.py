import unittest
from server import Server
import socket
import threading
import time

def wait_for_condition(check_function, timeout=5, interval=0.1):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_function():
            return True
        time.sleep(interval)
    return False


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
        self.send_command("/exit")

    def test_malformed_command(self):
        response = self.send_command("/msg")
        self.assertEqual(response, "/msg failed")
        self.send_command("/exit")

    def test_username_taken(self):
        self.send_command("/username user1")
        response = self.send_command("/username user1")
        self.assertEqual(response, "/username taken")
        self.send_command("/exit")

    def test_create_and_join_room(self):
        self.send_command("/username test2")
        response = self.send_command("/create #testroom")
        self.assertEqual(response, "/create ok")
        response = self.send_command("/join #testroom")
        self.assertEqual(response, "/join ok")
        self.send_command("/exit")

    def test_msg(self):
        self.send_command("/username test3")
        self.send_command("/create #testroom")
        self.send_command("/join #testroom")
        response = self.send_command("/msg Hello from test3")
        self.assertEqual(response, "/msg sent")
        self.send_command("/exit")

    def test_msgs(self):
        self.send_command("/username test4")
        self.send_command("/join #welcome")
        self.send_command("/msg Hello from test4")
        time.sleep(1)
        response = self.send_command("/msgs")
        self.assertIn("Hello from test4", response)
        self.send_command("/exit")

    def test_multiple_clients(self):
        # User 1 setup
        response = self.send_command("/username user11")
        self.assertEqual(response, "/username ok")
        response = self.send_command("/create #room6")
        self.assertEqual(response, "/create ok")
        response = self.send_command("/join #room6")
        self.assertEqual(response, "/join ok")

        # User 2 setup
        client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client2.connect(('127.0.0.1', 12345))
        client2.recv(1024)  # Receive username prompt
        client2.sendall(b"/username user12\n")
        client2.recv(1024)  # Receive confirmation
        client2.sendall(b"/join #room6\n")
        client2.recv(1024)  # Receive join confirmation

        # User 1 sends a message
        response = self.send_command("/msg Hello from user11")
        self.assertEqual(response, "/msg sent")

        # User 2 sends a message
        client2.sendall(b"/msg Hello from user12\n")
        client2.recv(1024)  # Receive message sent confirmation

        # Wait for both messages to be present
        def check_messages():
            response = self.send_command("/msgs")
            return "(user11 @#room6) Hello from user11" in response and "(user12 @#room6) Hello from user12" in response

        # Poll for condition with a timeout
        self.assertTrue(wait_for_condition(check_messages), "Messages from both users were not found in time.")

        # Clean up
        self.send_command("/exit")
        client2.sendall(b"/exit\n")
        client2.close()
    	
    def test_private_messages(self):
        self.send_command("/username user24")
        self.send_command("/join #welcome")

        client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client2.connect(('127.0.0.1', 12345))
        client2.recv(1024)
        client2.sendall(b"/username user25\n")
        client2.recv(1024)

        self.send_command("/pmsg user25 Hello from user24")
        client2.sendall(b"/pmsg user24 Hello from user25\n")

        # Check private messages for both users
        response_user24 = self.send_command("/pmsgs")
        self.assertIn("Hello from user25", response_user24)

        response_user25 = client2.recv(1024).decode().strip()
        self.assertIn("Hello from user24", response_user25)

        self.send_command("/exit")
        client2.sendall(b"/exit\n")
        client2.close()

    def test_join_non_existent_room(self):
        response = self.send_command("/username user26")
        response = self.send_command("/join #nonexistentroom")
        self.assertEqual(response, "/join no_room")
        self.send_command("/exit")

    def test_create_existing_room(self):
        response = self.send_command("/username user27")
       
        response = self.send_command("/create #welcome")
        self.assertEqual(response, "/create room_exists")
        self.send_command("/exit")


if __name__ == "__main__":
    unittest.main()
