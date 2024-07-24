import socket
import threading
from database import db, User, Room, Message, PrivateMessage

class Server:
    allowed_logged_out_commands = {'/login', '/register', '/help'}
    
    def __init__(self, host='127.0.0.1', port=12345):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(5)
        self.clients = {}  # Maps usernames to connections
        self.session = db.get_session()
        self.logged_in_users = {}  # Maps connections to usernames
        self.user_rooms = {}  # Maps usernames to their current rooms
        self.commands = {
            '/register': self.handle_register,
            '/login': self.handle_login,
            '/create': self.handle_create,
            '/join': self.handle_join,
            '/msg': self.handle_msg,
            '/msgs': self.handle_msgs,
            '/pmsg': self.handle_pmsg,
            '/pmsgs': self.handle_pmsgs,
            '/help': self.handle_help,
            '/exit': self.handle_exit,
            '/room': self.handle_room,
            '/rooms': self.handle_rooms,
            '/users': self.handle_users,
            '/allusers': self.handle_allusers
        }

    def start(self):
        print("Server started...")
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.handle_client, args=(conn,)).start()

    def handle_client(self, conn):
        conn.sendall("Welcome to the chat server!\n".encode())
        conn.sendall("Use /login <username> <password>.\n".encode())
        conn.sendall("Use /register <username> <password> to create a new account.\n".encode())
        
        while True:
            try:
                data = conn.recv(1024).decode().strip()
                if not data:
                    break
                
                command, *args = data.split()
                username = self.logged_in_users.get(conn)
                
                if command not in Server.allowed_logged_out_commands and not username:
                    response = "/login required"
                elif command in self.commands:
                    response = self.commands[command](args, username, conn)
                else:
                    response = "Invalid command use /help for a list of commands"

                conn.sendall((response + '\n').encode())

                if command == '/login' and response == '/login ok':
                    self.clients[username] = conn
                    self.logged_in_users[conn] = username
                    self.user_rooms[username] = None  # No room initially
                elif command == '/exit' and username:
                    if username in self.clients:
                        del self.clients[username]
                    if conn in self.logged_in_users:
                        del self.logged_in_users[conn]
                    if username in self.user_rooms:
                        del self.user_rooms[username]

            except Exception as e:
                print(f"Error: {e}")
                break

        # Clean up on disconnect
        username = self.logged_in_users.pop(conn, None)
        if username and username in self.clients:
            del self.clients[username]
        if username in self.user_rooms:
            del self.user_rooms[username]
        conn.close()

    def handle_register(self, args, username, conn):
        if len(args) != 2:
            return '/register invalid'
        new_username, password = args
        if self.session.query(User).filter_by(username=new_username).first():
            return '/register username_taken'
        user = User(username=new_username)
        user.set_password(password)
        self.session.add(user)
        self.session.commit()
        return '/register ok'

    def handle_login(self, args, username, conn):
        if len(args) != 2:
            return '/login invalid'
        login_username, password = args
        user = self.session.query(User).filter_by(username=login_username).first()
        if not user or not user.check_password(password):
            return '/login invalid'
        if login_username in self.clients:
            return '/login already_logged_in'
        self.clients[login_username] = conn
        self.logged_in_users[conn] = login_username
        self.user_rooms[login_username] = None  # No room initially
        return '/login ok'

    def handle_create(self, args, username, conn):
        if len(args) != 1 or not args[0].startswith('#'):
            return '/create invalid'
        room_name = args[0]
        if self.session.query(Room).filter_by(room=room_name).first():
            return '/create exists'
        room = Room(room=room_name)
        self.session.add(room)
        self.session.commit()
        return '/create ok'

    def handle_join(self, args, username, conn):
        if len(args) != 1 or not args[0].startswith('#'):
            return '/join invalid'
        room_name = args[0]
        room = self.session.query(Room).filter_by(room=room_name).first()
        if not room:
            return '/join nonexistent'
        user = self.session.query(User).filter_by(username=username).first()
        if room not in user.rooms:
            user.rooms.append(room)
            self.session.commit()
            self.user_rooms[username] = room_name
            return '/join ok'
        else:
            return '/join already_member'

    def handle_msg(self, args, username, conn):
        if len(args) < 2 or not args[0].startswith('#'):
            return '/msg invalid'
        room_name = args[0]
        room = self.session.query(Room).filter_by(room=room_name).first()
        if not room:
            return '/msg nonexistent'
        message_text = ' '.join(args[1:])
        message = Message(room_id=room_name, username=username, message=message_text)
        self.session.add(message)
        self.session.commit()
        for user in room.users:
            if user.username in self.clients:
                self.clients[user.username].sendall((f"{username}: {message_text}\n").encode())
        return '/msg sent'

    def handle_msgs(self, args, username, conn):
        if len(args) != 1 or not args[0].startswith('#'):
            return '/msgs invalid'
        room_name = args[0]
        room = self.session.query(Room).filter_by(room=room_name).first()
        if not room:
            return '/msgs nonexistent'
        messages = self.session.query(Message).filter_by(room_id=room_name).all()
        return '\n'.join([f"{msg.username}: {msg.message}" for msg in messages]) if messages else "/msgs none"

    def handle_pmsg(self, args, username, conn):
        if len(args) < 2:
            return '/pmsg invalid'
        to_user = args[0]
        message_text = ' '.join(args[1:])
        if not self.session.query(User).filter_by(username=to_user).first():
            return '/pmsg nonexistent'
        private_message = PrivateMessage(to_user=to_user, from_user=username, message=message_text)
        self.session.add(private_message)
        self.session.commit()
        if to_user in self.clients:
            self.clients[to_user].sendall((f"{username}: {message_text}\n").encode())
        return '/pmsg sent'

    def handle_pmsgs(self, args, username, conn):
        messages = self.session.query(PrivateMessage).filter_by(to_user=username).all()
        return '\n'.join([f"{msg.from_user}: {msg.message}" for msg in messages]) if messages else "/pmsgs none"

    def handle_help(self, args, username, conn):
        help_text = (
            "/login <username> <password> - Login with existing credentials\n"
            "/register <username> <password> - Register a new account\n"
            "/create <#room> - Create a new room\n"
            "/join <#room> - Join a room\n"
            "/msg <#room> <message> - Send a message to a room\n"
            "/msgs <#room> - Show messages in a room\n"
            "/pmsg <user> <message> - Send a private message\n"
            "/pmsgs - Show private messages\n"
            "/exit - Exit the server\n"
            "/room - Show current room\n"
            "/rooms - List all rooms\n"
            "/users <#room> - List users in a room\n"
            "/allusers - List all users\n"
        )
        return help_text

    def handle_exit(self, args, username, conn):
        if username in self.clients:
            del self.clients[username]
        if conn in self.logged_in_users:
            del self.logged_in_users[conn]
        if username in self.user_rooms:
            del self.user_rooms[username]
        return '/exit ok'

    def handle_room(self, args, username, conn):
        current_room = self.user_rooms.get(username)
        if current_room:
            return f"Current room: {current_room}"
        else:
            return "/room not_in_room"

    def handle_rooms(self, args, username, conn):
        rooms = self.session.query(Room).all()
        return '\n'.join([room.room for room in rooms]) if rooms else "/rooms none"

    def handle_users(self, args, username, conn):
        if len(args) != 1:
            return '/users invalid'
        room_name = args[0]
        room = self.session.query(Room).filter_by(room=room_name).first()
        if not room:
            return '/users nonexistent'
        users = [user.username for user in room.users]
        return '\n'.join(users) if users else "/users none"

    def handle_allusers(self, args, username, conn):
        users = self.session.query(User).all()
        return '\n'.join([user.username for user in users]) if users else "/allusers none"

if __name__ == "__main__":
    server = Server()
    server.start()
