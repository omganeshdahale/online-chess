# Online chess
Online chess in Django

LINK: https://chess.centralindia.cloudapp.azure.com

## Getting started
### Requirements
 - Python 3.6+
 - PIP
 - venv
 - Redis

### Installation
```
# Clone the repository
git clone https://github.com/omganeshdahale/online-chess.git

# Enter into the directory
cd chat-app/

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install the dependencies
pip install -r requirements.txt

# Apply migrations.
python manage.py migrate
```
### Starting the application
```
python manage.py runserver
```
### Starting redis server
```
redis-server
```
