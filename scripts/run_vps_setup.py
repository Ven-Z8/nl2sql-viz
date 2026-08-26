"""Run the VPS setup.sh with generated secrets (no nested-quote issues)."""
import re
import secrets
import subprocess

key = re.search(r"OPENROUTER_API_KEY=(\S+)", open(".env", encoding="utf-8").read()).group(1)
pg_pass = secrets.token_hex(16)
sec_key = secrets.token_hex(32)

remote = (
    "cd /opt/nl2sql-viz/deploy && "
    f"export POSTGRES_PASSWORD={pg_pass} && "
    f"export OPENROUTER_API_KEY={key} && "
    f"export SECRET_KEY={sec_key} && "
    "nohup bash setup.sh > setup.log 2>&1 & echo STARTED"
)
cmd = [
    "ssh", "-i", r"C:\Users\venki\.ssh\nl2sql_vps",
    "-o", "ConnectTimeout=15", "root@162.216.113.78", remote,
]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
print("STDOUT:", r.stdout.strip())
print("STDERR:", r.stderr.strip()[:300])
print("RC:", r.returncode)