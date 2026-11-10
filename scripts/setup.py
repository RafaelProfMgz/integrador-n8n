#!/usr/bin/env python3
"""Create local configuration without overwriting existing secrets."""
from pathlib import Path
import os
import secrets

root = Path(__file__).resolve().parents[1]
target = root / '.env'
content = (root / '.env.example').read_text()
content = content.replace('POSTGRES_PASSWORD=CHANGE_ME', 'POSTGRES_PASSWORD=' + secrets.token_hex(32))
content = content.replace('N8N_ENCRYPTION_KEY=CHANGE_ME', 'N8N_ENCRYPTION_KEY=' + secrets.token_hex(32))
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('.env existente preservado.')
else:
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)
    print('.env criado com segredos aleatorios e permissao 600.')
