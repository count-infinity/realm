# Quick Start

This guide gets you from zero to a running REALM server in 5 minutes.

## Start the Server

```bash
# Activate your virtual environment
source venv/bin/activate

# Start with default settings
realm start
```

You should see:

```
Starting REALM...
Database initialized at game.db
Loaded 1 objects from database
Telnet server listening on 0.0.0.0:4000
REALM game server started
```

## Connect

Open a new terminal and connect via telnet:

```bash
telnet localhost 4000
```

You'll see the welcome screen:

```
============================================================
  Welcome to REALM
  Real-time Event-Action Layered MUD
============================================================

Enter 'connect <name> <password>' to log in
Enter 'create <name> <password>' to create a new character
```

## Create a Character

```
create Alice secret123
```

You're now in the game! Try some commands:

```
look        # See the room
who         # See who's online
say Hello!  # Say something
help        # List commands
quit        # Disconnect
```

## Custom Welcome Screen

Create a `config/welcome.txt` file to customize:

```bash
mkdir -p config
cat > config/welcome.txt << 'EOF'

    ╔═══════════════════════════════════════╗
    ║     Welcome to My Awesome MUD!        ║
    ╚═══════════════════════════════════════╝

    Type 'connect <name> <password>' to log in
    Type 'create <name> <password>' to register

EOF
```

Restart the server to see your custom screen.

## Next Steps

- [Your First Game](first-game.md) - Create rooms, items, and NPCs
- [Architecture Overview](../architecture/overview.md) - Understand how REALM works
