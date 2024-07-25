import unittest
import socket
import threading
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from server import Server
from database import Database

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
        cls.server.server.close()
        cls.server_thread.join()

        cls.session.close()
        cls.db.engine.dispose()

        if os.path.exists(DATABASE_PATH):
            os.remove(DATABASE_PATH)

    def setUp(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(('127.0.0.1', 12345))
        self.client.recv(1024)  # Read initial prompt

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

if __name__ == "__main__":
    unittest.main()
