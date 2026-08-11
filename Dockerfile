FROM python:3.12-slim

WORKDIR /app

# Python deps from pyproject
COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY data ./data
RUN pip install --no-cache-dir "fastapi>=0.135.2" "uvicorn[standard]>=0.42.0" \
    "asyncpg>=0.31.0" "nooa>=0.0.8" "sqlglot>=30.15.0" "python-dotenv>=1.2.2" \
    "python-multipart>=0.0.32" "aiosqlite>=0.22.1" "argon2-cffi>=25.1.0" \
    "cryptography>=46.0.5" "passlib[bcrypt]>=1.7.4" "duckdb>=1.5.5" "openpyxl>=3.1.5"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]