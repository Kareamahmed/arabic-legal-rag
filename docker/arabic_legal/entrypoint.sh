#!/bin/bash
set -e

cd /app/models/db_schemes/arabic_legal/
alembic upgrade head
cd /app

exec "$@"