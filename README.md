# 7 Days to Die Server Management Tool

A Python-based command-line interface for managing and monitoring 7 Days to Die dedicated servers via Telnet. Not all functionality fully tested.

## Features

### Server Management
- 🎮 **Real-time monitoring** - Track player logins, logouts, and chat messages
- 👥 **Player management** - List online players, give items, teleport players
- 📦 **Item bundles** - Create reusable item packages for quick distribution
- 🏷️ **Player aliases** - Simplify commands with short aliases for player names
- 📊 **Statistics tracking** - Monitor playtime, session counts, and player activity
- ⏰ **Day management** - Safely change game day/time with safeguards

### Safety Features
- ⚠️ Prevents accidental time travel (going backwards in days)
- 🔒 Confirmation prompts for dangerous operations
- 📝 Database logging of all player sessions

## Requirements

- Python 3.10+
- 7 Days to Die Dedicated Server with Telnet enabled
- PostgreSQL (optional, for database features)

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/7dtd-server-manager.git
cd 7dtd-server-manager
```

2. **Install dependencies:**
```bash
pip install psycopg2-binary
```

3. **Configure your server:**

Create a `.env` file from the template:
```bash
cp .env.example .env
```

Edit `.env` with your server details:
```ini
SERVER_HOST=your_server_ip
SERVER_PORT=8081
SERVER_PASSWORD=your_telnet_password

# Optional: Database configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=7dtd
DB_USER=postgres
DB_PASSWORD=your_db_password
```

4. **Enable Telnet on your 7DTD server:**

Edit your `serverconfig.xml`:
```xml
<property name="TelnetEnabled" value="true"/>
<property name="TelnetPort" value="8081"/>
<property name="TelnetPassword" value="your_secure_password"/>
```

5. **Set up database (optional):**

If you want to use player aliases, bundles, and stats tracking:
```bash
# Option 1: Let the script create tables automatically
createdb 7dtd
python 7dtd_cli.py  # Tables created on first connection

# Option 2: Use the SQL setup script
psql -U postgres -f setup_database.sql
```

**Note:** The Python script will automatically create all necessary tables on first run, so the SQL setup file is optional.

# Tables will be created automatically on first run
```

## Usage

Start the tool:
```bash
python 7dtd_cli.py
```

### Quick Start Commands
```bash
# List online players
players

# Give items to a player
give "Player Name" ak47 1 6
give PlayerAlias steelArrow 100 6

# Teleport players
tp PlayerName 0 100 0
tpto PlayerName OtherPlayer

# Broadcast messages
say Server restart in 5 minutes!

# Check game day
getday

# Set game day (safely)
setday 42
setday 42 14 30  # Day 42 at 14:30
```

## Advanced Features

### Player Aliases

Create shortcuts for player names:
```bash
# Create an alias
alias "Revlin McAwesome" Revlin

# Now use the alias in any command
give Revlin ak47 1 6
tp Revlin 0 100 0

# List all aliases
aliases

# Remove an alias
unalias Revlin
```

### Item Bundles

Create reusable item packages:
```bash
# Create a bundle
bundle create MedKit "Emergency medical supplies"

# Add items to the bundle
bundle add MedKit medicalFirstAidKit 5 6
bundle add MedKit drugPainkillers 10 6
bundle add MedKit drugSteroids 5 6

# Give the entire bundle to a player
givebundle PlayerName MedKit

# List all bundles
bundle list

# Show bundle contents
bundle show MedKit
```

### Player Statistics

Track player activity:
```bash
# View player stats
stats PlayerName

# Shows:
# - Total sessions
# - Total playtime
# - Average session length
# - Last seen
```

### Day Management

Safely manage game time:
```bash
# Get current day
getday

# Set day (prevents going backwards)
setday 50

# Set day with specific time
setday 50 14 30  # Day 50 at 14:30

# Force override (with confirmation)
setday 1 8 0 force
```

## Available Commands

### Connection
- `connect <host> <port> <password>` - Connect to server manually
- `disconnect` - Disconnect from server
- `exit` / `quit` - Exit the program

### Player Management
- `players` - List online players
- `give <player> <item> <qty> <quality>` - Give items to player
- `givebundle <player> <bundle>` - Give item bundle to player
- `spawn <player> <entity> <count>` - Spawn entities near player
- `tp <player> <x> <y> <z>` - Teleport to coordinates
- `tpto <player> <target>` - Teleport player to another player
- `say <message>` - Broadcast message to all players

### Aliases
- `alias <full_name> <alias>` - Create player alias
- `unalias <alias>` - Remove alias
- `aliases` - List all aliases
- `stats <player>` - Show player statistics

### Bundles
- `bundle create <name> [desc]` - Create new bundle
- `bundle add <bundle> <item> <qty> <quality>` - Add item to bundle
- `bundle show <name>` - Show bundle contents
- `bundle list` - List all bundles
- `bundle delete <name>` - Delete bundle
- `bundle remove <bundle> <item>` - Remove item from bundle

### Server
- `getday` - Get current game day and time
- `setday <day> [hour] [minute] [force]` - Set game day/time
- `cmd <command>` - Send raw server command
- `items` - Show common item names
- `entities` - Show common entity IDs
- `debug [on|off]` - Toggle debug mode

## Database Schema

The tool automatically creates these tables:

- `player_aliases` - Player name aliases
- `player_sessions` - Login/logout tracking
- `item_bundles` - Custom item bundle definitions
- `bundle_items` - Items within bundles

## Troubleshooting

### Connection Issues
- Verify Telnet is enabled in `serverconfig.xml`
- Check firewall allows port 8081
- Ensure password matches exactly

### Player Names with Spaces
Use quotes around player names:
```bash
give "Player Name" item 1 6
```

Or create an alias:
```bash
alias "Player Name" PlayerName
give PlayerName item 1 6
```

### Database Features Not Working
- Install psycopg2: `pip install psycopg2-binary`
- Verify PostgreSQL is running
- Check database credentials in `.env`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - feel free to use and modify as needed.

## Credits

Created for the 7 Days to Die community to make server administration easier and more efficient.

## Disclaimer

This tool is not affiliated with or endorsed by The Fun Pimps. Use at your own risk. Always backup your server before making major changes.
