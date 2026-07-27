#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE airflow;
    CREATE DATABASE mlflow;
    CREATE DATABASE telemetry;
EOSQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "telemetry" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS timescaledb;
EOSQL
