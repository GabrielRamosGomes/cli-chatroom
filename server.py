import socket
import threading
from collections import defaultdict, deque
from database import Database, User, Room, Message, PrivateMessage, db, user_room_table

class Server:
    def __init__(self, host='127.0.0.1', port=12345, session=None):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(5)
        self.rooms = {}
        self.clients = {}
        self.lock = threading.Lock()
        self.messages = defaultdict(deque)
        self.private_messages = defaultdict(deque)
        self.session = session if session else db.get_session()
        self.commands = {
            '/username': self.handle_username,
            '/exit': self.handle_exit,
            '/room': self.handle_room,
            '/rooms': self.handle_rooms,
            '/create': self.handle_create,
            '/join': self.handle_join,
            '/users': self.handle_users,
            '/allusers': self.handle_allusers,
            '/msg': self.handle_msg,
            '/msgs': self.handle_msgs,
            '/pmsg': self.handle_pmsg,
            '/pmsgs': self.handle_pmsgs,
            '/help': self.handle_help,
        }

    def create_welcome_room(self):
        welcome_room = self.session.query(Room).filter_by(room='#welcome').first()
        if not welcome_room:
            new_room = Room(room='#welcome')
            self.session.add(new_room)
            self.session.commit()
            self.rooms['#welcome'] = new_room

    def start(self):
        self.create_welcome_room()
        print("Server started...")
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()

    def handle_client(self, conn):
        conn.sendall(b"/username required\n")
        username = None
        while True:
            try:
                msg = conn.recv(1024).decode().strip()
                if not msg:
                    continue

                command, *args = msg.split(' ', 1)
                args = args[0] if args else ""
                
                if command in self.commands:
                    response = self.commands[command](args, username, conn)
                else:
                    response = "/unknown command"

                if command == '/username' and response == '/username ok':
                    with self.lock:
                        username = args
                        self.clients[username] = conn

                if command == '/exit':
                    if username:
                        self.remove_user_from_rooms(username)
                        conn.sendall(response.encode() + b'\n')
                        conn.close()
                        break

                conn.sendall(response.encode() + b'\n')
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"Error: {e}")
                break
        conn.close()

    def handle_username(self, args, username, conn):
        if not args:
            return "/username required"
        if self.session.query(User).filter_by(username=args).first():
            return "/username taken"
        
        new_user = User(username=args)
        self.session.add(new_user)
        self.session.commit()
        self.clients[args] = conn

        return "/username ok"

    def handle_exit(self, args, username, conn):
        return "/exit ok"

    def handle_room(self, args, username, conn):
        user = self.session.query(User).filter_by(username=username).first()
        if user:  
            room = self.get_user_room(user)
            return f"/room {room.room}" if room else "/room none"

        return "/room none"

    def handle_rooms(self, args, username, conn):
        rooms = self.session.query(Room).all()
        room_names = [room.room for room in rooms]
        return f"/rooms {', '.join(room_names)}"

    def handle_create(self, args, username, conn):
        if not args:
            return "/create room_required"
        if self.session.query(Room).filter_by(room=args).first():
            return "/create room_exists"
       
        if not args.startswith("#"):
            return "/create invalid_room, must start with #"

        new_room = Room(room=args)
        self.session.add(new_room)
        self.session.commit()
        
        return "/create ok"

    def handle_join(self, args, username, conn):
        if not args:
            return "/join no_room"
        
        room = self.session.query(Room).filter_by(room=args).first()
        if not room:
            return "/join no_room"
        
        with self.lock:
            user = self.session.query(User).filter_by(username=username).first()
            room.users.append(user)
            self.session.commit()
       
        return "/join ok"

    def handle_users(self, args, username, conn):
        user = self.session.query(User).filter_by(username=username).first()
        room = self.get_user_room(user)
        if room:
            users = [user.username for user in room.users]
            return f"/users {', '.join(users)}"
        return "/users none"

    def handle_allusers(self, args, username, conn):
        rooms = self.session.query(Room).all()
        all_users = [f"{user.username}@{room.room}" for room in rooms for user in room.users]
        return f"/allusers {', '.join(all_users)}"

    def handle_msg(self, args, username, conn):
        user = self.session.query(User).filter_by(username=username).first()
        room = self.get_user_room(user)

        if room:
            with self.lock:
                message = Message(room_id=room.id, username=username, message=args)
                self.session.add(message)
                self.session.commit()
                self.messages[room].append(message)

                for user in room.users:
                    if user.username != username:
                        self.clients[user.username].sendall((f"({username} @{room.room}) {args}" + '\n').encode())
           
            return "/msg sent"
        return "/msg failed"

    def handle_msgs(self, args, username, conn):
        user = self.session.query(User).filter_by(username=username).first()
        room = self.get_user_room(user)
        if room:
            messages = self.session.query(Message).filter_by(room_id=room.id).all()
            
            if not messages:
                return "/msgs none"
            
            message_texts = "\n".join(f"({msg.username} @{room.room}) {msg.message}" for msg in messages)
            self.session.query(Message).filter_by(room_id=room.id).delete()
            self.session.commit()
            
            return f"/msgs\n{message_texts}"
        
        return "/msgs none"

    def handle_pmsg(self, args, username, conn):
        if len(args.split(' ', 1)) < 2:
            return "/pmsg usage"
       
        recipient, private_msg = args.split(' ', 1)
       
        if not self.session.query(User).filter_by(username=recipient).first():
            return "/pmsg no_user"
       
        private_message = PrivateMessage(to_user=recipient, from_user=username, message=private_msg)
        self.session.add(private_message)
        self.session.commit()
        
        if recipient in self.clients:
            self.clients[recipient].sendall((f"({username} @private) {private_msg}" + '\n').encode())
        
        return "/pmsg sent"

    def handle_pmsgs(self, args, username, conn):
        private_messages = self.session.query(PrivateMessage).filter_by(to_user=username).all()
        
        if not private_messages:
            return "/pmsgs none"
       
        message_texts = "\n".join(f"({pm.from_user} @private) {pm.message}" for pm in private_messages)
        self.session.query(PrivateMessage).filter_by(to_user=username).delete()
        self.session.commit()
        
        return f"/pmsgs\n{message_texts}"

    def handle_help(self, args, username, conn):
        return ("/help: Show this help message\n"
                "/username <name>: Assigns a username\n"
                "/exit: Ends the session\n"
                "/room: Shows current room\n"
                "/rooms: Lists all available rooms\n"
                "/create <room>: Creates a new room\n"
                "/join <room>: Joins an existing room\n"
                "/users: Lists users in the current room\n"
                "/allusers: Lists all users and their respective rooms\n"
                "/msg <message>: Sends a message to the current room\n"
                "/msgs: Retrieves messages from the queue\n"
                "/pmsg <username> <message>: Sends a private message\n"
                "/pmsgs: Retrieves private messages from the queue\n")

    def get_user_room(self, user):
        return self.session.query(Room).join(user_room_table).filter(user_room_table.c.user_id == user.id).first()

    def remove_user_from_rooms(self, username):
        user = self.session.query(User).filter_by(username=username).first()
        if user:
            for room in user.rooms:
                room.users.remove(user)
            self.session.commit()

if __name__ == "__main__":
    server = Server()
    server.start()