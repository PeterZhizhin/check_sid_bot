import os

# DATABASE_URL = "postgresql://username:password@localhost/database_name"
DATABASE_URL = "sqlite:///mydatabase.db"
BOT_TOKEN = os.environ["CHECK_SID_BOT_TOKEN"]

MAX_RECORDS_PER_USER = 5
