#!/bin/bash
# Initialize Hive Metastore Database

# Start PostgreSQL
su - postgres -c 'pg_ctl -D /var/lib/postgresql/data start'
sleep 3

# Create user and database
su - postgres -c "psql -c \"CREATE USER hive WITH PASSWORD 'hive';\""
su - postgres -c "psql -c \"CREATE DATABASE metastore OWNER hive;\""
su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE metastore TO hive;\""

echo "Hive metastore database initialized!"
