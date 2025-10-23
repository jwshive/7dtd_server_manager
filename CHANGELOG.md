# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-10-18

### Initial Release

#### Added
- **Server Connection**
  - Telnet-based connection to 7 Days to Die dedicated servers
  - Auto-connect from `.env` configuration file
  - Connection status monitoring

- **Player Management**
  - List online players with IDs
  - Give items to players with custom quantity and quality
  - Spawn entities near players
  - Teleport players to coordinates
  - Teleport player to another player
  - Broadcast messages to all players

- **Player Aliases System**
  - Create short aliases for player names with spaces
  - Alias resolution works in all commands automatically
  - List all configured aliases
  - Remove aliases
  - Persistent storage in PostgreSQL database

- **Item Bundle System**
  - Create reusable item bundles
  - Add multiple items to bundles with quantities and quality levels
  - Give entire bundles to players with one command
  - List all available bundles
  - Show detailed bundle contents
  - Delete bundles
  - Remove individual items from bundles
  - Persistent storage in PostgreSQL database

- **Player Statistics Tracking**
  - Automatic session logging (login/logout times)
  - Total playtime tracking
  - Session count tracking
  - Average session length calculation
  - Last seen timestamp
  - Persistent storage in PostgreSQL database

- **Real-time Event Monitoring**
  - Player login notifications with timestamps
  - Player logout notifications with session duration
  - Chat message monitoring with timestamps
  - Automatic session duration calculation and logging
  - Debug mode for troubleshooting server messages

- **Day/Time Management**
  - Get current game day and time
  - Set game day and time with safety checks
  - Prevent accidental time travel (going backwards)
  - Force override with confirmation prompt
  - Custom time setting (hour and minute)

- **Command-line Interface**
  - Interactive shell with command history
  - Help system for all commands
  - Tab completion support
  - Clean, formatted output
  - Reference lists for common items and entities

- **Database Integration**
  - PostgreSQL support for persistent data
  - Automatic table creation on first run
  - Optional database features (works without database)
  - Database connection error handling

- **Safety Features**
  - Player name quoting for names with spaces
  - Day change safety checks (prevents going backwards)
  - Force confirmation prompts for dangerous operations
  - Connection validation before commands
  - Error handling and user-friendly messages

- **Developer Features**
  - Debug mode for monitoring server output
  - Raw command execution for testing
  - Configurable wait times for server responses
  - Thread-safe command execution

#### Technical Details
- Python 3.10+ support
- Socket-based telnet implementation (Python 3.13 compatible)
- Multi-threaded monitoring system
- Regex-based server response parsing
- PostgreSQL database with automatic schema management
- Environment variable configuration via `.env` file

#### Documentation
- Comprehensive README.md with installation and usage instructions
- .env.example template for easy configuration
- setup_database.sql for manual database setup
- Inline code documentation and docstrings
- Command help text for all commands

#### Files Included
- server_manager.py - Main application
- .env.example - Configuration template
- requirements.txt - Python dependencies
- setup_database.sql - Database schema
- README.md - Full documentation
- LICENSE - MIT License
- .gitignore - Git ignore rules

### Known Issues
- Logout detection may not capture all server message formats
- gettime command requires monitoring pause to avoid race conditions
- Player names with special characters may need additional handling

### Future Enhancements
- Discord bot integration
- Scheduled server restarts
- Automated backups
- Web dashboard
- Player achievement system
- Economy/points system
- Scheduled announcements
- AFK detection

---

## Version History

- **v1.0.0** (2025-10-18) - Initial public release
