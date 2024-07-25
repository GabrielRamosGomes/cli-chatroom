import unittest
import socket
import threading
import os
import time
from server import Server
from database import Database, User, user_room_table

def wait_for_condition(check_function, timeout=5, interval=0.1):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_function():
            return True
        time.sleep(interval)
    return False

DATABASE_PATH = 'test.db'
class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database(f'sqlite:///{DATABASE_PATH}')
        cls.session = cls.db.get_session()

        cls.server = Server(session=cls.session)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        
        wait_for_condition(lambda: cls.server.server.fileno() != -1) 
    
    @classmethod
    def tearDownClass(cls):
        if cls.session:
            cls.session.close()
        if cls.db and cls.db.engine:
            cls.db.engine.dispose()

        time.sleep(1)
        if os.path.exists(DATABASE_PATH):
            os.remove(DATABASE_PATH)

    def setUp(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(('127.0.0.1', 12345))
        self.client.recv(1024)

    def tearDown(self):
        self.client.close()
        self.session.query(User).delete()
        self.session.query(user_room_table).delete()

    def send_command(self, command):
        self.client.sendall(command.encode() + b'\n')
        response = self.client.recv(1024).decode().strip()
        return response

    def test_username(self):
        response = self.send_command("/username test")
        self.assertEqual(response, "/username ok")
        self.send_command("/exit")

    def test_username_taken(self):
        self.send_command("/username test")
        response = self.send_command("/username test")
        self.assertEqual(response, "/username taken")
        self.send_command("/exit")
    
    def test_malformed_msg(self):
        self.send_command("/username test")
        response = self.send_command("/msg")
        self.assertEqual(response, "/msg failed")
        self.send_command("/exit")

    def test_create_Join_room(self):
        self.send_command("/username test")
        response = self.send_command("/create #testroom")
        self.assertEqual(response, "/create ok")
        response = self.send_command("/join #testroom")
        self.assertEqual(response, "/join ok")
        self.send_command("/exit")

    def test_join_room_not_exists(self):
        self.send_command("/username test")
        response = self.send_command("/join #no_room")
        self.assertEqual(response, "/join no_room")

    def test_create_room_exists(self):
        self.send_command("/username test")
        response = self.send_command("/create #testroom")
        self.assertEqual(response, "/create room_exists")

    def test_msg(self):
        self.send_command("/username test")
        self.send_command("/create #testroom")
        self.send_command("/join #testroom")
        response = self.send_command("/msg Hello from test")
        self.assertEqual(response, "/msg sent")
        self.send_command("/exit")

    def test_msgs(self):
        self.send_command("/username test")
        self.send_command("/join #welcome")
        self.send_command("/msg Hello from test")
        response = self.send_command("/msgs")
        self.assertIn("Hello from test", response)
        self.send_command("/exit")

    def test_users(self):
        self.send_command("/username test")
        self.send_command("/join #welcome")
        response = self.send_command("/users")
        self.assertIn("test", response)
        self.send_command("/exit")

    def test_all_users(self):
        self.send_command("/username test")
        self.send_command("/join #welcome")

        response = self.send_command("/allusers")
        self.assertIn("test@#welcome", response)
        
if __name__ == "__main__":
    unittest.main()
