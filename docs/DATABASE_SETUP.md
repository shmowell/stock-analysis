# PostgreSQL Database Setup Guide

## Prerequisites

- PostgreSQL 12+ installed
- Python 3.9+ with pip
- Environment variables configured in `.env`

## Installation Steps

### 1. Install PostgreSQL

**Windows:**
- Download from: https://www.postgresql.org/download/windows/
- Or use Chocolatey: `choco install postgresql`

**Mac:**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. Configure PostgreSQL

Set PostgreSQL password (if not done during installation):

```bash
# Switch to postgres user (Linux/Mac)
sudo -u postgres psql

# Or on Windows, use psql from cmd/PowerShell
psql -U postgres

# Inside psql, set password
ALTER USER postgres WITH PASSWORD 'your_secure_password';
\q
```

### 3. Update .env File

Edit your `.env` file with your PostgreSQL credentials:

```env
# PostgreSQL Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=stock_analysis

# Or use connection string
DATABASE_URL=postgresql://postgres:your_secure_password@localhost:5432/stock_analysis
```

**IMPORTANT:** Never commit `.env` to version control!

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `psycopg2-binary` - PostgreSQL adapter
- `sqlalchemy` - SQL toolkit and ORM
- `alembic` - Database migrations

### 5. Run Database Setup

```bash
python scripts/setup_database.py
```

This script will:
1. Create the `stock_analysis` database (if it doesn't exist)
2. Create all tables from `scripts/init_db.sql`
3. Verify table creation
4. Report success/failure

Expected output:
```
============================================================
Stock Analysis Framework - Database Setup
============================================================
Connecting to PostgreSQL at localhost:5432
Database 'stock_analysis' already exists.
Creating SQLAlchemy engine for stock_analysis
Connected to PostgreSQL: PostgreSQL 15.x...
Creating database tables...
Tables created successfully from SQL script!
Verifying table creation...
All expected tables created successfully!
Tables: api_call_log, calculation_log, fundamental_data, ...
============================================================
Database setup complete!
============================================================
```

### 6. Test Connection

```bash
python -c "from src.database import test_connection; test_connection()"
```

Expected output:
```
Database connection successful!
```

## Troubleshooting

### Connection Refused

**Error:** `psycopg2.OperationalError: could not connect to server`

**Solutions:**
1. Check PostgreSQL is running:
   ```bash
   # Windows
   sc query postgresql

   # Mac
   brew services list

   # Linux
   sudo systemctl status postgresql
   ```

2. Verify port 5432 is correct:
   ```bash
   psql -U postgres -h localhost -p 5432
   ```

3. Check `pg_hba.conf` allows local connections:
   ```
   # Add this line if needed
   host    all             all             127.0.0.1/32            md5
   ```

### Authentication Failed

**Error:** `psycopg2.OperationalError: FATAL: password authentication failed`

**Solutions:**
1. Double-check password in `.env`
2. Reset PostgreSQL password:
   ```bash
   sudo -u postgres psql
   ALTER USER postgres WITH PASSWORD 'new_password';
   ```

### Database Already Exists Error

**Error:** `database "stock_analysis" already exists`

**Solutions:**
This is fine! The script checks and skips creation if it exists.

To start fresh:
```bash
# Drop and recreate database
sudo -u postgres psql
DROP DATABASE stock_analysis;
\q
python scripts/setup_database.py
```

### Missing Dependencies

**Error:** `ModuleNotFoundError: No module named 'psycopg2'`

**Solutions:**
```bash
pip install -r requirements.txt
```

If `psycopg2-binary` fails to install:
```bash
# Windows - install Visual C++ Build Tools
# Mac
brew install postgresql

# Linux
sudo apt-get install libpq-dev python3-dev
pip install psycopg2
```

## Database Management

### View Tables

```bash
psql -U postgres -d stock_analysis

# Inside psql
\dt          # List all tables
\d stocks    # Describe stocks table
\q           # Quit
```

### Manual SQL Execution

```bash
psql -U postgres -d stock_analysis -f scripts/init_db.sql
```

### Backup Database

```bash
# Backup
pg_dump -U postgres stock_analysis > backup_$(date +%Y%m%d).sql

# Restore
psql -U postgres -d stock_analysis < backup_20260212.sql
```

### Drop All Tables (Reset)

```bash
psql -U postgres -d stock_analysis

DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
\q

python scripts/setup_database.py
```

## Database Schema

See [database_schema.md](database_schema.md) for:
- Complete table definitions
- Relationships and indexes
- Data retention policies
- Performance considerations

## Next Steps

After successful setup:

1. ✅ Database created and tables initialized
2. ⏭️ Populate `stocks` table with universe
3. ⏭️ Begin API data collection (Phase 1)
4. ⏭️ Run score calculations
5. ⏭️ Use override system

## Advanced Configuration

### Connection Pooling

Already configured in `src/database/__init__.py`:
- Pool size: 5 connections
- Max overflow: 10
- Pool timeout: 30 seconds
- Pool recycle: 1 hour

### Alembic Migrations (Future)

Initialize Alembic for schema versioning:

```bash
alembic init alembic
```

Edit `alembic.ini`:
```ini
sqlalchemy.url = postgresql://postgres:password@localhost:5432/stock_analysis
```

Create first migration:
```bash
alembic revision --autogenerate -m "Initial tables"
alembic upgrade head
```

### Performance Tuning

For large datasets, edit `postgresql.conf`:
```
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
```

Restart PostgreSQL after changes.

## Security Best Practices

1. ✅ Never commit `.env` with passwords
2. ✅ Use strong passwords (minimum 16 characters)
3. ✅ Limit PostgreSQL network access (`pg_hba.conf`)
4. ✅ Regular backups (automated)
5. ⚠️ Consider SSL for production
6. ⚠️ Create separate users with limited permissions

## Getting Help

- PostgreSQL Documentation: https://www.postgresql.org/docs/
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
- Project Issues: https://github.com/shmowell/stock-analysis/issues
