#!/usr/bin/env python3
"""
Command-line tool for managing 7 Days to Die server.
Usage: python 7dtd_cli.py

Create a .env file with:
SERVER_HOST=192.168.1.172
SERVER_PORT=8081
SERVER_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=7dtd
DB_USER=postgres
DB_PASSWORD=your_db_password
"""

import socket
import time
import re
from typing import Optional, Callable
import threading
import cmd
import sys
from datetime import datetime
import os
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("Warning: psycopg2 not installed. Database features disabled. Install with: pip install psycopg2-binary")


class DatabaseManager:
    """Manages PostgreSQL database connection and operations."""

    def __init__(self, config):
        """Initialize database connection."""
        self.config = config
        self.conn = None

        if not POSTGRES_AVAILABLE:
            print("Database features disabled - psycopg2 not installed")
            return

        try:
            self.conn = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                dbname=config['dbname'],
                user=config['user'],
                password=config['password']
            )
            self.conn.autocommit = True
            self._init_tables()
            print(f"Connected to database: {config['dbname']}")
        except Exception as e:
            print(f"Database connection failed: {e}")
            self.conn = None

    def _init_tables(self):
        """Create necessary tables if they don't exist."""
        if not self.conn:
            return

        with self.conn.cursor() as cur:
            # Player aliases table
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS player_aliases
                        (
                            id
                            SERIAL
                            PRIMARY
                            KEY,
                            full_name
                            VARCHAR
                        (
                            255
                        ) NOT NULL UNIQUE,
                            alias VARCHAR
                        (
                            100
                        ) NOT NULL UNIQUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)

            # Player sessions table for tracking playtime
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS player_sessions
                        (
                            id
                            SERIAL
                            PRIMARY
                            KEY,
                            player_name
                            VARCHAR
                        (
                            255
                        ) NOT NULL,
                            login_time TIMESTAMP NOT NULL,
                            logout_time TIMESTAMP,
                            duration_seconds INTEGER,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)

            # Create index for faster lookups
            cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_player_name
                            ON player_sessions(player_name)
                        """)

            # Item bundles table
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS item_bundles
                        (
                            id
                            SERIAL
                            PRIMARY
                            KEY,
                            bundle_name
                            VARCHAR
                        (
                            100
                        ) NOT NULL UNIQUE,
                            description TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)

            # Bundle items table
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS bundle_items
                        (
                            id
                            SERIAL
                            PRIMARY
                            KEY,
                            bundle_id
                            INTEGER
                            NOT
                            NULL
                            REFERENCES
                            item_bundles
                        (
                            id
                        ) ON DELETE CASCADE,
                            item_name VARCHAR
                        (
                            255
                        ) NOT NULL,
                            quantity INTEGER NOT NULL DEFAULT 1,
                            quality INTEGER NOT NULL DEFAULT 1,
                            UNIQUE
                        (
                            bundle_id,
                            item_name
                        )
                            )
                        """)

    def get_full_name(self, alias_or_name: str) -> str:
        """Resolve an alias to full name, or return original if not aliased."""
        if not self.conn:
            return alias_or_name

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if it's an alias
            cur.execute("SELECT full_name FROM player_aliases WHERE alias = %s", (alias_or_name,))
            result = cur.fetchone()
            if result:
                return result['full_name']

            # Check if it's already a full name
            cur.execute("SELECT full_name FROM player_aliases WHERE full_name = %s", (alias_or_name,))
            result = cur.fetchone()
            if result:
                return result['full_name']

            # Not in database, return as-is
            return alias_or_name

    def add_alias(self, full_name: str, alias: str) -> bool:
        """Add or update a player alias."""
        if not self.conn:
            return False

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                            INSERT INTO player_aliases (full_name, alias)
                            VALUES (%s, %s) ON CONFLICT (full_name) 
                    DO
                            UPDATE SET alias = EXCLUDED.alias
                            """, (full_name, alias))
            return True
        except Exception as e:
            print(f"Error adding alias: {e}")
            return False

    def remove_alias(self, alias: str) -> bool:
        """Remove a player alias."""
        if not self.conn:
            return False

        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM player_aliases WHERE alias = %s", (alias,))
                return cur.rowcount > 0
        except Exception as e:
            print(f"Error removing alias: {e}")
            return False

    def list_aliases(self) -> list:
        """Get all player aliases."""
        if not self.conn:
            return []

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT full_name, alias FROM player_aliases ORDER BY alias")
            return cur.fetchall()

    def log_login(self, player_name: str, login_time: datetime):
        """Log a player login."""
        if not self.conn:
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                            INSERT INTO player_sessions (player_name, login_time)
                            VALUES (%s, %s)
                            """, (player_name, login_time))
        except Exception as e:
            print(f"Error logging login: {e}")

    def log_logout(self, player_name: str, logout_time: datetime, duration_seconds: int):
        """Log a player logout and update session duration."""
        if not self.conn:
            return

        try:
            with self.conn.cursor() as cur:
                # Update the most recent session for this player
                cur.execute("""
                            UPDATE player_sessions
                            SET logout_time      = %s,
                                duration_seconds = %s
                            WHERE player_name = %s
                              AND logout_time IS NULL ORDER BY login_time DESC
                    LIMIT 1
                            """, (logout_time, duration_seconds, player_name))
        except Exception as e:
            print(f"Error logging logout: {e}")

    def get_player_stats(self, player_name: str) -> dict:
        """Get statistics for a player."""
        if not self.conn:
            return {}

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT COUNT(*)              as total_sessions,
                               SUM(duration_seconds) as total_playtime_seconds,
                               AVG(duration_seconds) as avg_session_seconds,
                               MAX(login_time)       as last_seen
                        FROM player_sessions
                        WHERE player_name = %s
                          AND logout_time IS NOT NULL
                        """, (player_name,))
            return cur.fetchone() or {}

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def create_bundle(self, bundle_name: str, description: str = '') -> bool:
        """Create a new item bundle."""
        if not self.conn:
            return False

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                            INSERT INTO item_bundles (bundle_name, description)
                            VALUES (%s, %s) ON CONFLICT (bundle_name) DO NOTHING
                    RETURNING id
                            """, (bundle_name, description))
                result = cur.fetchone()
                return result is not None
        except Exception as e:
            print(f"Error creating bundle: {e}")
            return False

    def add_item_to_bundle(self, bundle_name: str, item_name: str, quantity: int = 1, quality: int = 1) -> bool:
        """Add an item to a bundle."""
        if not self.conn:
            return False

        try:
            with self.conn.cursor() as cur:
                # Get bundle ID
                cur.execute("SELECT id FROM item_bundles WHERE bundle_name = %s", (bundle_name,))
                result = cur.fetchone()
                if not result:
                    print(f"Bundle '{bundle_name}' not found")
                    return False

                bundle_id = result[0]

                # Add item to bundle
                cur.execute("""
                            INSERT INTO bundle_items (bundle_id, item_name, quantity, quality)
                            VALUES (%s, %s, %s, %s) ON CONFLICT (bundle_id, item_name) 
                    DO
                            UPDATE SET quantity = EXCLUDED.quantity, quality = EXCLUDED.quality
                            """, (bundle_id, item_name, quantity, quality))
                return True
        except Exception as e:
            print(f"Error adding item to bundle: {e}")
            return False

    def get_bundle(self, bundle_name: str) -> dict:
        """Get bundle details and items."""
        if not self.conn:
            return None

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get bundle info
                cur.execute("""
                            SELECT id, bundle_name, description
                            FROM item_bundles
                            WHERE bundle_name = %s
                            """, (bundle_name,))
                bundle = cur.fetchone()

                if not bundle:
                    return None

                # Get bundle items
                cur.execute("""
                            SELECT item_name, quantity, quality
                            FROM bundle_items
                            WHERE bundle_id = %s
                            """, (bundle['id'],))
                items = cur.fetchall()

                return {
                    'name': bundle['bundle_name'],
                    'description': bundle['description'],
                    'items': items
                }
        except Exception as e:
            print(f"Error getting bundle: {e}")
            return None

    def list_bundles(self) -> list:
        """List all item bundles."""
        if not self.conn:
            return []

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT b.bundle_name, b.description, COUNT(bi.id) as item_count
                        FROM item_bundles b
                                 LEFT JOIN bundle_items bi ON b.id = bi.bundle_id
                        GROUP BY b.id, b.bundle_name, b.description
                        ORDER BY b.bundle_name
                        """)
            return cur.fetchall()

    def delete_bundle(self, bundle_name: str) -> bool:
        """Delete a bundle and all its items."""
        if not self.conn:
            return False

        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM item_bundles WHERE bundle_name = %s", (bundle_name,))
                return cur.rowcount > 0
        except Exception as e:
            print(f"Error deleting bundle: {e}")
            return False

    def remove_item_from_bundle(self, bundle_name: str, item_name: str) -> bool:
        """Remove an item from a bundle."""
        if not self.conn:
            return False

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                            DELETE
                            FROM bundle_items
                            WHERE bundle_id = (SELECT id FROM item_bundles WHERE bundle_name = %s)
                              AND item_name = %s
                            """, (bundle_name, item_name))
                return cur.rowcount > 0
        except Exception as e:
            print(f"Error removing item from bundle: {e}")
            return False


class SevenDTDServer:
    """Controller for 7 Days to Die dedicated server via Telnet."""

    def __init__(self, host: str = 'localhost', port: int = 8081, password: str = '', db_manager=None):
        """
        Initialize connection to 7DTD server.

        Args:
            host: Server hostname or IP
            port: Telnet port (default 8081, set in serverconfig.xml)
            password: Telnet password (set in serverconfig.xml)
            db_manager: DatabaseManager instance for aliasing and logging
        """
        self.host = host
        self.port = port
        self.password = password
        self.sock = None
        self.connected = False
        self.monitor_thread = None
        self.monitoring = False
        self.command_lock = threading.Lock()
        self.debug_mode = False
        self.player_sessions = {}  # Track player login times
        self.db = db_manager

    def connect(self) -> bool:
        """Establish connection to the server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.host, self.port))

            # Wait for password prompt
            self._read_until(b"Please enter password:")

            # Send password
            self.sock.sendall(self.password.encode('ascii') + b"\r\n")

            # Wait for successful login
            response = self._read_until(b"Press 'help' for help", timeout=5)

            if b"Password incorrect" in response:
                print("Authentication failed!")
                self.sock.close()
                return False

            # Set socket to non-blocking for monitoring
            self.sock.setblocking(False)

            self.connected = True
            print(f"Connected to {self.host}:{self.port}")
            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            if self.sock:
                self.sock.close()
            return False

    def _read_until(self, expected: bytes, timeout: float = 5.0) -> bytes:
        """Read data until expected string is found."""
        data = b""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if expected in data:
                    return data
            except socket.timeout:
                continue
            except BlockingIOError:
                time.sleep(0.1)
                continue

        return data

    def disconnect(self):
        """Close the connection."""
        self.stop_monitoring()
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.connected = False
        print("Disconnected from server")

    def send_command(self, command: str, wait_time: float = 0.5) -> str:
        """
        Send a command to the server and return the response.

        Args:
            command: The command to send
            wait_time: Time to wait for response in seconds

        Returns:
            Server response as string
        """
        if not self.connected:
            return "Not connected to server"

        with self.command_lock:  # Prevent monitor from interfering
            try:
                # Send command
                self.sock.sendall(command.encode('ascii') + b"\r\n")

                # Give server time to process
                time.sleep(wait_time)

                # Read available data with multiple attempts
                response = b""
                self.sock.settimeout(2.0)
                attempts = 0
                max_attempts = 5

                while attempts < max_attempts:
                    try:
                        chunk = self.sock.recv(4096)
                        if chunk:
                            response += chunk
                            attempts = 0  # Reset if we got data
                        else:
                            break
                    except socket.timeout:
                        attempts += 1
                        if response:  # We got some data already
                            break
                        time.sleep(0.1)
                        continue

                # Set back to non-blocking for monitoring
                self.sock.setblocking(False)

                decoded = response.decode('ascii', errors='ignore')
                return decoded
            except Exception as e:
                self.sock.setblocking(False)
                return f"Error sending command: {e}"

    def get_players(self) -> list:
        """Get list of online players."""
        response = self.send_command("listplayers")
        players = []

        # Parse player list from response
        lines = response.split('\n')
        for line in lines:
            # Format: "0. id=171, Revlin McAwesome, pos=(-933.9, 76.1, 1757.7), ..."
            # Match pattern: number. id=XXX, PlayerName, pos=...
            match = re.search(r'\d+\.\s+id=(\d+),\s+([^,]+),\s+pos=', line)
            if match:
                players.append({
                    'id': match.group(1),
                    'name': match.group(2).strip()
                })

        return players

    def give_item(self, player_name: str, item_name: str, quantity: int = 1, quality: int = 1):
        """
        Give an item to a player.

        Args:
            player_name: Name of the player (or alias)
            item_name: Item name (e.g., 'steelArrow', 'medicalBandage')
            quantity: Number of items
            quality: Item quality/level
        """
        # Resolve alias to full name
        if self.db:
            player_name = self.db.get_full_name(player_name)

        # Wrap player name in quotes if it contains spaces
        if ' ' in player_name:
            player_name = f'"{player_name}"'

        command = f"give {player_name} {item_name} {quantity} {quality}"
        response = self.send_command(command)
        print(response)
        return response

    def give_bundle(self, player_name: str, bundle_name: str):
        """
        Give all items from a bundle to a player.

        Args:
            player_name: Name of the player (or alias)
            bundle_name: Name of the bundle
        """
        if not self.db:
            print("Database not configured")
            return False

        # Get bundle details
        bundle = self.db.get_bundle(bundle_name)
        if not bundle:
            print(f"Bundle '{bundle_name}' not found")
            return False

        # Resolve alias to full name
        player_name = self.db.get_full_name(player_name)

        print(f"Giving bundle '{bundle_name}' to {player_name}...")

        # Give each item in the bundle
        success_count = 0
        for item in bundle['items']:
            # Wrap player name in quotes if it contains spaces
            quoted_name = f'"{player_name}"' if ' ' in player_name else player_name
            command = f"give {quoted_name} {item['item_name']} {item['quantity']} {item['quality']}"
            response = self.send_command(command, wait_time=0.3)

            if "ERR" not in response and "Wrong" not in response:
                success_count += 1
                print(f"  ✓ {item['item_name']} x{item['quantity']} (Q{item['quality']})")
            else:
                print(f"  ✗ {item['item_name']} - {response.strip()}")

        print(f"\nBundle complete: {success_count}/{len(bundle['items'])} items given")
        return success_count == len(bundle['items'])

    def spawn_entity(self, player_name: str, entity_id: str, count: int = 1):
        """
        Spawn an entity near a player.

        Args:
            player_name: Target player name (or alias)
            entity_id: Entity ID (e.g., 'zombieSteve', 'animalBear')
            count: Number to spawn
        """
        # Resolve alias to full name
        if self.db:
            player_name = self.db.get_full_name(player_name)

        # Wrap player name in quotes if it contains spaces
        if ' ' in player_name:
            player_name = f'"{player_name}"'

        command = f"spawnentity {player_name} {entity_id} {count}"
        response = self.send_command(command)
        print(response)
        return response

    def teleport_player(self, player_name: str, x: int, y: int, z: int):
        """Teleport a player to coordinates."""
        # Resolve alias to full name
        if self.db:
            player_name = self.db.get_full_name(player_name)

        # Wrap player name in quotes if it contains spaces
        if ' ' in player_name:
            player_name = f'"{player_name}"'

        command = f"tele {player_name} {x} {y} {z}"
        response = self.send_command(command)
        print(response)
        return response

    def teleport_player_to_player(self, player_name: str, target_player: str):
        """Teleport a player to another player."""
        # Resolve aliases to full names
        if self.db:
            player_name = self.db.get_full_name(player_name)
            target_player = self.db.get_full_name(target_player)

        # Wrap player names in quotes if they contain spaces
        if ' ' in player_name:
            player_name = f'"{player_name}"'
        if ' ' in target_player:
            target_player = f'"{target_player}"'

        command = f"teleportplayer {player_name} {target_player}"
        response = self.send_command(command)
        print(response)
        return response

    def broadcast_message(self, message: str):
        """Send a message to all players."""
        command = f'say "{message}"'
        response = self.send_command(command)
        return response

    def get_current_day(self) -> int:
        """Get the current game day."""
        time_info = self.get_current_time()
        if time_info:
            return time_info[0]
        return None

    def get_current_time(self) -> tuple:
        """Get the current game day and time."""
        # Temporarily pause monitoring to avoid race condition
        was_monitoring = self.monitoring
        if was_monitoring:
            self.monitoring = False
            time.sleep(0.2)  # Let monitor thread finish current iteration

        try:
            response = self.send_command("gettime", wait_time=1.5)

            # Parse response: "Day 7, 14:23"
            match = re.search(r'Day\s+(\d+),\s+(\d+):(\d+)', response, re.MULTILINE | re.DOTALL)
            if match:
                return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            return None
        finally:
            # Resume monitoring
            if was_monitoring:
                self.monitoring = True

    def set_day(self, day: int, hour: int = 8, minute: int = 0, force: bool = False) -> tuple[bool, str]:
        """
        Set the game day and time with safety checks.

        Args:
            day: Day number to set
            hour: Hour (0-23, default 8 for morning)
            minute: Minute (0-59, default 0)
            force: If True, bypass safety checks

        Returns:
            Tuple of (success, message)
        """
        if day < 1:
            return False, "Error: Day must be 1 or greater"

        if not (0 <= hour <= 23):
            return False, "Error: Hour must be between 0 and 23"

        if not (0 <= minute <= 59):
            return False, "Error: Minute must be between 0 and 59"

        # Get current day for safety check
        current_day = self.get_current_day()

        if current_day is None:
            if not force:
                return False, "Error: Could not determine current day. Use force=True to override."
        elif day < current_day and not force:
            return False, f"Error: Cannot set day backwards from {current_day} to {day}. This would reset progress. Use 'setday {day} {hour} {minute} force' to override."

        # Set the day and time
        command = f"settime {day} {hour} {minute}"
        response = self.send_command(command)

        if "ERR" in response or "Error" in response:
            return False, f"Error setting time: {response}"

        return True, f"Time set to Day {day}, {hour:02d}:{minute:02d}"

    def start_monitoring(self, on_login: Optional[Callable] = None,
                         on_logout: Optional[Callable] = None,
                         on_chat: Optional[Callable] = None):
        """
        Start monitoring server events in a separate thread.

        Args:
            on_login: Callback function(player_name) for player logins
            on_logout: Callback function(player_name, duration) for player logouts
            on_chat: Callback function(player_name, message) for chat messages
        """
        if self.monitoring:
            print("Already monitoring")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(on_login, on_logout, on_chat),
            daemon=True
        )
        self.monitor_thread.start()
        print("Started monitoring server events")

    def stop_monitoring(self):
        """Stop the monitoring thread."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

    def _monitor_loop(self, on_login, on_logout, on_chat):
        """Internal method to monitor server output."""
        while self.monitoring and self.connected:
            try:
                data = b""
                try:
                    self.sock.settimeout(0.5)  # Shorter timeout for more responsive monitoring
                    chunk = self.sock.recv(4096)
                    if chunk:
                        data += chunk
                except socket.timeout:
                    # Timeout is normal, just continue
                    time.sleep(0.1)
                    continue
                except BlockingIOError:
                    time.sleep(0.1)
                    continue

                if not data:
                    time.sleep(0.1)
                    continue

                text = data.decode('ascii', errors='ignore')
                lines = text.split('\n')

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Debug mode: print all lines
                    if self.debug_mode:
                        print(f"\n[DEBUG] {line}")

                    # Player login: "INF PlayerLogin: PlayerName/V X.X" or "INF RequestToEnterGame: .../PlayerName"
                    if on_login:
                        if "PlayerLogin:" in line:
                            match = re.search(r'PlayerLogin:\s+([^/]+)', line)
                            if match:
                                player_name = match.group(1).strip()
                                login_time = datetime.now()
                                self.player_sessions[player_name] = time.time()
                                if self.db:
                                    self.db.log_login(player_name, login_time)
                                on_login(player_name)
                        elif "RequestToEnterGame:" in line:
                            match = re.search(r'RequestToEnterGame:.*?/(.+)', line)
                            if match:
                                player_name = match.group(1).strip()
                                login_time = datetime.now()
                                self.player_sessions[player_name] = time.time()
                                if self.db:
                                    self.db.log_login(player_name, login_time)
                                on_login(player_name)

                    # Player logout: "Player disconnected: EntityID=..., PlayerID='...', OwnerID='...', PlayerName='...'"
                    if "Player disconnected" in line and on_logout:
                        # Try multiple patterns for different server versions
                        match = re.search(r"PlayerName='([^']+)'", line)
                        if not match:
                            match = re.search(r'PlayerName=([^,\s]+)', line)
                        if not match:
                            match = re.search(r'Player disconnected:\s+([^,\(]+)', line)

                        if match:
                            player_name = match.group(1).strip()
                            session_duration = None
                            if player_name in self.player_sessions:
                                session_duration = time.time() - self.player_sessions[player_name]
                                del self.player_sessions[player_name]
                                if self.db and session_duration:
                                    logout_time = datetime.now()
                                    self.db.log_logout(player_name, logout_time, int(session_duration))
                            on_logout(player_name, session_duration)

                    # Chat message: "Chat: 'PlayerName': message" or "Chat (from ...): PlayerName: message"
                    if "Chat" in line and on_chat:
                        # Try pattern with quotes first
                        match = re.search(r"Chat.*?'([^']+)':\s*(.+)", line)
                        if not match:
                            # Try pattern without quotes
                            match = re.search(r"Chat.*?:\s*([^:]+):\s*(.+)", line)

                        if match:
                            player_name = match.group(1).strip()
                            message = match.group(2).strip()
                            on_chat(player_name, message)

            except Exception as e:
                if "timed out" not in str(e).lower():
                    print(f"Monitor error: {e}")
                time.sleep(1)


class DTDCommandLine(cmd.Cmd):
    """Interactive command-line interface for 7DTD server management."""

    intro = """
╔═══════════════════════════════════════════════╗
║   7 Days to Die Server Management Tool        ║
║   Type 'help' for available commands          ║
╚═══════════════════════════════════════════════╝
    """
    prompt = '7DTD> '

    def __init__(self):
        super().__init__()
        self.server = None
        self.connected = False
        self.env_config = self._load_env()
        self.debug_monitor = False  # Debug flag for monitoring
        self.db = None

        # Initialize database if config present
        if self.env_config and 'db' in self.env_config:
            self.db = DatabaseManager(self.env_config['db'])

        # Auto-connect if .env exists
        if self.env_config:
            print(f"Found .env configuration for {self.env_config['host']}")
            print("Connecting automatically...")
            self._auto_connect()

    def _load_env(self):
        """Load configuration from .env file."""
        env_path = Path('.env')
        if not env_path.exists():
            return None

        config = {}
        db_config = {}
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")

                        if key == 'SERVER_HOST':
                            config['host'] = value
                        elif key == 'SERVER_PORT':
                            config['port'] = int(value)
                        elif key == 'SERVER_PASSWORD':
                            config['password'] = value
                        elif key == 'DB_HOST':
                            db_config['host'] = value
                        elif key == 'DB_PORT':
                            db_config['port'] = int(value)
                        elif key == 'DB_NAME':
                            db_config['dbname'] = value
                        elif key == 'DB_USER':
                            db_config['user'] = value
                        elif key == 'DB_PASSWORD':
                            db_config['password'] = value

            # Check if we have all required server fields
            if 'host' in config and 'port' in config and 'password' in config:
                # Add database config if complete
                if len(db_config) == 5:  # All 5 DB fields present
                    config['db'] = db_config
                return config
            else:
                print("Warning: .env file incomplete. Need SERVER_HOST, SERVER_PORT, and SERVER_PASSWORD")
                return None

        except Exception as e:
            print(f"Error reading .env file: {e}")
            return None

    def _auto_connect(self):
        """Automatically connect using .env configuration."""
        if not self.env_config:
            return

        self.server = SevenDTDServer(
            self.env_config['host'],
            self.env_config['port'],
            self.env_config['password'],
            db_manager=self.db
        )

        if self.server.connect():
            self.connected = True
            self.prompt = f"7DTD[{self.env_config['host']}]> "

            # Start monitoring
            self.server.start_monitoring(
                on_login=self._on_login,
                on_logout=self._on_logout,
                on_chat=self._on_chat
            )
        else:
            print("Auto-connect failed! Use 'connect' command manually.")

    def do_connect(self, arg):
        """Connect to server: connect <host> <port> <password>"""
        args = arg.split()

        if len(args) < 3:
            print("Usage: connect <host> <port> <password>")
            print("Example: connect localhost 8081 mypassword")
            return

        host, port, password = args[0], int(args[1]), args[2]

        self.server = SevenDTDServer(host, port, password, db_manager=self.db)

        if self.server.connect():
            self.connected = True
            self.prompt = f'7DTD[{host}]> '

            # Start monitoring
            self.server.start_monitoring(
                on_login=self._on_login,
                on_logout=self._on_logout,
                on_chat=self._on_chat
            )
        else:
            print("Failed to connect!")

    def do_disconnect(self, arg):
        """Disconnect from server"""
        if self.server:
            self.server.disconnect()
            self.connected = False
            self.prompt = '7DTD> '
            print("Disconnected")

    def do_players(self, arg):
        """List online players"""
        if not self._check_connection():
            return

        response = self.server.send_command("listplayers", wait_time=1.0)

        # Debug: show raw response
        if arg == "debug":
            print(f"Raw response:\n{repr(response)}\n")

        players = self.server.get_players()
        if players:
            print(f"\nOnline Players ({len(players)}):")
            for player in players:
                print(f"  - {player['name']} (ID: {player['id']})")
        else:
            print("No players online")
            if arg == "debug":
                print("\nTrying to parse response...")
                print(f"Response length: {len(response)}")
                print(f"Response lines: {response.split(chr(10))}")

    def do_give(self, arg):
        """Give item to player: give <player> <item> [quantity] [quality]
        Use quotes for player names with spaces: give "Player Name" item 10 6"""
        if not self._check_connection():
            return

        # Parse arguments, handling quoted strings
        args = self._parse_args(arg)

        if len(args) < 2:
            print("Usage: give <player> <item> [quantity] [quality]")
            print('Example: give "Revlin McAwesome" steelArrow 100 6')
            print('Or with alias: give Revlin steelArrow 100 6')
            return

        player = args[0]
        item = args[1]
        quantity = int(args[2]) if len(args) > 2 else 1
        quality = int(args[3]) if len(args) > 3 else 1

        self.server.give_item(player, item, quantity, quality)

    def do_spawn(self, arg):
        """Spawn entity: spawn <player> <entity_id> [count]
        Use quotes for player names with spaces: spawn "Player Name" zombieSteve 5"""
        if not self._check_connection():
            return

        args = self._parse_args(arg)

        if len(args) < 2:
            print("Usage: spawn <player> <entity_id> [count]")
            print('Example: spawn "Revlin McAwesome" zombieSteve 5')
            print('Or with alias: spawn Revlin zombieSteve 5')
            return

        player = args[0]
        entity = args[1]
        count = int(args[2]) if len(args) > 2 else 1

        self.server.spawn_entity(player, entity, count)

    def do_tp(self, arg):
        """Teleport player: tp <player> <x> <y> <z>
        Use quotes for player names with spaces: tp "Player Name" 100 50 200"""
        if not self._check_connection():
            return

        args = self._parse_args(arg)

        if len(args) < 4:
            print("Usage: tp <player> <x> <y> <z>")
            print('Example: tp "Revlin McAwesome" 100 50 -200')
            print('Or with alias: tp Revlin 100 50 -200')
            return

        player = args[0]
        x, y, z = int(args[1]), int(args[2]), int(args[3])

        self.server.teleport_player(player, x, y, z)

    def do_tpto(self, arg):
        """Teleport player to another player: tpto <player> <target_player>
        Use quotes for player names with spaces: tpto "Player 1" "Player 2" """
        if not self._check_connection():
            return

        args = self._parse_args(arg)

        if len(args) < 2:
            print("Usage: tpto <player> <target_player>")
            print('Example: tpto "Revlin McAwesome" "Other Player"')
            print('Or with aliases: tpto Revlin OtherPlayer')
            return

        player = args[0]
        target = args[1]

        self.server.teleport_player_to_player(player, target)

    def do_say(self, arg):
        """Broadcast message: say <message> [as <sender>]

        Examples:
          say Server restart in 5 minutes
          say Welcome to the server! as ServerBot"""
        if not self._check_connection():
            return

        if not arg:
            print("Usage: say <message> [as <sender>]")
            print("\nExamples:")
            print("  say Server restart in 5 minutes")
            print("  say Welcome! as ServerBot")
            print("  say Check the rules as Admin")
            return

        # Check if "as <sender>" is specified
        sender = None
        if ' as ' in arg:
            parts = arg.split(' as ', 1)
            message = parts[0].strip()
            sender = parts[1].strip()
        else:
            message = arg

        self.server.broadcast_message(message, sender)

        if sender:
            print(f"Broadcast as '{sender}': {message}")
        else:
            print(f"Broadcast: {message}")

    def do_cmd(self, arg):
        """Send raw command: cmd <command>"""
        if not self._check_connection():
            return

        if not arg:
            print("Usage: cmd <command>")
            return

        response = self.server.send_command(arg, wait_time=1.0)
        if response and response.strip():
            print(response)
        else:
            print("(No response or empty response)")

    def do_items(self, arg):
        """Show common item names"""
        items = {
            "Weapons": ["pistol", "shotgun", "ak47", "sniperRifle", "steelArrow"],
            "Medical": ["medicalBandage", "firstAidBandage", "painkillers"],
            "Food": ["canBeef", "canChili", "bottledWater"],
            "Resources": ["resourceWood", "resourceIron", "resourceCoal"],
            "Tools": ["pickaxeSteel", "shovelSteel", "fireaxeSteel"],
            "Ammo": ["ammo9mm", "ammoShotgunShell", "ammo762mm"]
        }

        print("\nCommon Item Names:")
        for category, item_list in items.items():
            print(f"\n{category}:")
            for item in item_list:
                print(f"  - {item}")

    def do_entities(self, arg):
        """Show common entity IDs"""
        entities = {
            "Zombies": ["zombieSteve", "zombieMarlene", "zombieArlene", "zombieFeral"],
            "Animals": ["animalBear", "animalDireWolf", "animalBoar", "animalChicken"],
            "Special": ["zombieScreamer", "zombieCop", "zombieSpider"]
        }

        print("\nCommon Entity IDs:")
        for category, entity_list in entities.items():
            print(f"\n{category}:")
            for entity in entity_list:
                print(f"  - {entity}")

    def do_debug(self, arg):
        """Toggle debug mode for monitoring: debug [on|off]"""
        if not self._check_connection():
            return

        if arg.lower() in ['on', 'true', '1', 'yes']:
            self.debug_monitor = True
            self.server.debug_mode = True
            print("Debug mode enabled - will show all server messages")
        elif arg.lower() in ['off', 'false', '0', 'no']:
            self.debug_monitor = False
            self.server.debug_mode = False
            print("Debug mode disabled")
        else:
            self.debug_monitor = not self.debug_monitor
            self.server.debug_mode = self.debug_monitor
            status = "enabled" if self.debug_monitor else "disabled"
            print(f"Debug mode {status}")

    def do_alias(self, arg):
        """Manage player aliases: alias <full_name> <alias>"""
        if not self.db:
            print("Database not configured. Add DB_* settings to .env file")
            return

        args = self._parse_args(arg)

        if len(args) < 2:
            print("Usage: alias <full_name> <alias>")
            print('Example: alias "Revlin McAwesome" Revlin')
            return

        full_name = args[0]
        alias = args[1]

        if self.db.add_alias(full_name, alias):
            print(f"✓ Aliased '{full_name}' to '{alias}'")
            print(f"You can now use '{alias}' in commands instead of '{full_name}'")
        else:
            print("Failed to create alias")

    def do_unalias(self, arg):
        """Remove a player alias: unalias <alias>"""
        if not self.db:
            print("Database not configured")
            return

        if not arg:
            print("Usage: unalias <alias>")
            return

        if self.db.remove_alias(arg):
            print(f"✓ Removed alias '{arg}'")
        else:
            print(f"Alias '{arg}' not found")

    def do_aliases(self, arg):
        """List all player aliases"""
        if not self.db:
            print("Database not configured")
            return

        aliases = self.db.list_aliases()

        if aliases:
            print("\nPlayer Aliases:")
            print(f"{'Alias':<20} {'Full Name':<30}")
            print("-" * 50)
            for row in aliases:
                print(f"{row['alias']:<20} {row['full_name']:<30}")
        else:
            print("No aliases configured")

    def do_stats(self, arg):
        """Show player statistics: stats <player_name_or_alias>"""
        if not self.db:
            print("Database not configured")
            return

        if not arg:
            print("Usage: stats <player_name_or_alias>")
            return

        # Resolve alias
        player_name = self.db.get_full_name(arg)
        stats = self.db.get_player_stats(player_name)

        if not stats or not stats.get('total_sessions'):
            print(f"No statistics found for '{player_name}'")
            return

        print(f"\nStatistics for {player_name}:")
        print(f"  Total sessions: {stats['total_sessions']}")

        if stats['total_playtime_seconds']:
            total_hours = int(stats['total_playtime_seconds'] // 3600)
            total_minutes = int((stats['total_playtime_seconds'] % 3600) // 60)
            print(f"  Total playtime: {total_hours}h {total_minutes}m")

        if stats['avg_session_seconds']:
            avg_minutes = int(stats['avg_session_seconds'] // 60)
            print(f"  Average session: {avg_minutes}m")

        if stats['last_seen']:
            print(f"  Last seen: {stats['last_seen']}")

    def do_bundle(self, arg):
        """Create or modify item bundles: bundle <create|add|show|list|delete|remove>"""
        if not self.db:
            print("Database not configured")
            return

        args = self._parse_args(arg)

        if not args:
            print("Usage: bundle <create|add|show|list|delete|remove> [args...]")
            print("\nCommands:")
            print("  bundle create <name> [description]  - Create a new bundle")
            print("  bundle add <bundle> <item> <qty> <quality> - Add item to bundle")
            print("  bundle show <name>                  - Show bundle contents")
            print("  bundle list                         - List all bundles")
            print("  bundle delete <name>                - Delete a bundle")
            print("  bundle remove <bundle> <item>       - Remove item from bundle")
            return

        cmd = args[0].lower()

        if cmd == 'create':
            if len(args) < 2:
                print("Usage: bundle create <name> [description]")
                return

            bundle_name = args[1]
            description = ' '.join(args[2:]) if len(args) > 2 else ''

            if self.db.create_bundle(bundle_name, description):
                print(f"✓ Created bundle '{bundle_name}'")
            else:
                print(f"Failed to create bundle (may already exist)")

        elif cmd == 'add':
            if len(args) < 5:
                print("Usage: bundle add <bundle> <item> <quantity> <quality>")
                print("Example: bundle add MedKit medicalFirstAidKit 5 6")
                return

            bundle_name = args[1]
            item_name = args[2]
            quantity = int(args[3])
            quality = int(args[4])

            if self.db.add_item_to_bundle(bundle_name, item_name, quantity, quality):
                print(f"✓ Added {item_name} x{quantity} (Q{quality}) to '{bundle_name}'")
            else:
                print("Failed to add item to bundle")

        elif cmd == 'show':
            if len(args) < 2:
                print("Usage: bundle show <name>")
                return

            bundle_name = args[1]
            bundle = self.db.get_bundle(bundle_name)

            if not bundle:
                print(f"Bundle '{bundle_name}' not found")
                return

            print(f"\nBundle: {bundle['name']}")
            if bundle['description']:
                print(f"Description: {bundle['description']}")
            print(f"\nItems ({len(bundle['items'])}):")
            for item in bundle['items']:
                print(f"  - {item['item_name']} x{item['quantity']} (Quality {item['quality']})")

        elif cmd == 'list':
            bundles = self.db.list_bundles()

            if not bundles:
                print("No bundles configured")
                return

            print("\nItem Bundles:")
            print(f"{'Name':<20} {'Items':<8} {'Description':<40}")
            print("-" * 70)
            for bundle in bundles:
                desc = bundle['description'] or ''
                if len(desc) > 37:
                    desc = desc[:37] + '...'
                print(f"{bundle['bundle_name']:<20} {bundle['item_count']:<8} {desc:<40}")

        elif cmd == 'delete':
            if len(args) < 2:
                print("Usage: bundle delete <name>")
                return

            bundle_name = args[1]
            if self.db.delete_bundle(bundle_name):
                print(f"✓ Deleted bundle '{bundle_name}'")
            else:
                print(f"Bundle '{bundle_name}' not found")

        elif cmd == 'remove':
            if len(args) < 3:
                print("Usage: bundle remove <bundle> <item>")
                return

            bundle_name = args[1]
            item_name = args[2]

            if self.db.remove_item_from_bundle(bundle_name, item_name):
                print(f"✓ Removed {item_name} from '{bundle_name}'")
            else:
                print("Failed to remove item")

        else:
            print(f"Unknown bundle command: {cmd}")
            print("Use 'bundle' with no args to see available commands")

    def do_givebundle(self, arg):
        """Give a bundle to a player: givebundle <player> <bundle>"""
        if not self._check_connection():
            return

        if not self.db:
            print("Database not configured")
            return

        args = self._parse_args(arg)

        if len(args) < 2:
            print("Usage: givebundle <player> <bundle>")
            print("Example: givebundle Revlin MedKit")
            print("\nUse 'bundle list' to see available bundles")
            return

        player = args[0]
        bundle_name = args[1]

        self.server.give_bundle(player, bundle_name)

    def do_getday(self, arg):
        """Get the current game day and time"""
        if not self._check_connection():
            return

        time_info = self.server.get_current_time()

        if time_info:
            day, hour, minute = time_info
            print(f"Current game time: Day {day}, {hour:02d}:{minute:02d}")
        else:
            print("Could not determine current time")

            # Show raw response for debugging if requested
            if arg == "debug":
                response = self.server.send_command("gettime", wait_time=1.0)
                print(f"Raw response: {repr(response)}")

    def do_setday(self, arg):
        """Set the game day and time: setday <day> [hour] [minute] [force]
        Safety: Prevents setting day backwards unless 'force' is specified

        Examples:
          setday 42              - Set to day 42, 08:00 (morning)
          setday 42 14 30        - Set to day 42, 14:30 (afternoon)
          setday 1 8 0 force     - Force set to day 1 (dangerous!)"""
        if not self._check_connection():
            return

        args = arg.split()

        if len(args) < 1:
            print("Usage: setday <day> [hour] [minute] [force]")
            print("\nExamples:")
            print("  setday 42              - Set to day 42, 08:00")
            print("  setday 42 14 30        - Set to day 42, 14:30")
            print("  setday 42 22 0         - Set to day 42, 22:00 (night)")
            print("  setday 1 8 0 force     - Force set to day 1 (dangerous!)")
            print("\nDefaults: hour=8, minute=0")
            print("Safety: Command prevents going backwards unless 'force' is used")
            return

        try:
            day = int(args[0])
            hour = 8  # Default to morning
            minute = 0
            force = False

            # Parse optional hour
            if len(args) > 1:
                if args[1].lower() == 'force':
                    force = True
                else:
                    hour = int(args[1])

            # Parse optional minute
            if len(args) > 2:
                if args[2].lower() == 'force':
                    force = True
                else:
                    minute = int(args[2])

            # Check for force flag
            if len(args) > 3 and args[3].lower() == 'force':
                force = True

        except ValueError:
            print("Error: Day, hour, and minute must be numbers")
            return

        # Warn about force
        if force:
            print("⚠️  WARNING: Using 'force' bypasses safety checks!")
            print(f"You are about to set time to Day {day}, {hour:02d}:{minute:02d}")
            confirmation = input("Are you sure you want to continue? (yes/no): ")
            if confirmation.lower() != 'yes':
                print("Cancelled")
                return

        success, message = self.server.set_day(day, hour, minute, force)

        if success:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")

    def do_exit(self, arg):
        """Exit the program"""
        if self.db:
            self.db.close()
        if self.server:
            self.server.disconnect()
        print("Goodbye!")
        return True

    def do_quit(self, arg):
        """Exit the program"""
        return self.do_exit(arg)

    def _check_connection(self):
        """Check if connected to server"""
        if not self.connected:
            print("Not connected! Use 'connect' command first.")
            return False
        return True

    def _parse_args(self, arg):
        """Parse arguments handling quoted strings."""
        import shlex
        try:
            return shlex.split(arg)
        except ValueError:
            # If shlex fails, fall back to simple split
            return arg.split()

    def _on_login(self, player_name):
        """Handle player login event"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] ✓ {player_name} joined the server")
        print(self.prompt, end='', flush=True)

    def _on_logout(self, player_name, session_duration=None):
        """Handle player logout event"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if session_duration is not None:
            # Format duration as hours:minutes:seconds
            hours = int(session_duration // 3600)
            minutes = int((session_duration % 3600) // 60)
            seconds = int(session_duration % 60)

            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"

            print(f"\n[{timestamp}] ✗ {player_name} left the server (played for {duration_str})")
        else:
            print(f"\n[{timestamp}] ✗ {player_name} left the server")

        print(self.prompt, end='', flush=True)

    def _on_chat(self, player_name, message):
        """Handle chat message event"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] 💬 {player_name}: {message}")
        print(self.prompt, end='', flush=True)

    def emptyline(self):
        """Do nothing on empty line"""
        pass


if __name__ == '__main__':
    try:
        DTDCommandLine().cmdloop()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Exiting...")
        sys.exit(0)