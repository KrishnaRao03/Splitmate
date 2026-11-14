"""Encrypt (or decrypt) the secrets in Splitmate-Web/.env with Windows DPAPI.

Usage, from Splitmate-Web with the venv active:

    python scripts/protect_env.py                 encrypt the sensitive values
    python scripts/protect_env.py --add-field-key also create FIELD_ENCRYPTION_KEY if it's missing
    python scripts/protect_env.py --decrypt       turn everything back into plain text
    python scripts/protect_env.py --check         say which values are encrypted, without changing anything

Values are never printed. Only the Windows user who ran this can decrypt them.
"""
import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)

from env_crypto import SENSITIVE_KEYS, is_protected, protect_value, unprotect_value  # noqa: E402


def parse_line(line):
    stripped = line.strip()
    if not stripped or stripped.startswith('#') or '=' not in stripped:
        return None, None
    key, value = stripped.split('=', 1)
    return key.strip().lstrip('﻿'), value.strip().strip('"').strip("'")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--env-file', default=os.path.join(BASE_DIR, '.env'))
    parser.add_argument('--decrypt', action='store_true', help='write all values back as plain text')
    parser.add_argument('--check', action='store_true', help='report only, change nothing')
    parser.add_argument('--add-field-key', action='store_true', help='add FIELD_ENCRYPTION_KEY if it is missing')
    args = parser.parse_args()

    if not os.path.exists(args.env_file):
        sys.exit(f'No .env file at {args.env_file}')

    with open(args.env_file, encoding='utf-8') as env_file:
        lines = env_file.read().splitlines()

    keys = {parse_line(line)[0] for line in lines}
    if args.add_field_key and 'FIELD_ENCRYPTION_KEY' not in keys and not args.decrypt:
        from cryptography.fernet import Fernet
        lines.append('FIELD_ENCRYPTION_KEY=' + Fernet.generate_key().decode())
        print('Added a new FIELD_ENCRYPTION_KEY. Back it up: without it, payment details in the database cannot be read.')

    output, changed = [], []
    for line in lines:
        key, value = parse_line(line)
        if key is None or not value:
            output.append(line)
            continue

        if args.check:
            if key in SENSITIVE_KEYS or is_protected(value):
                print(f'{key}: {"encrypted" if is_protected(value) else "PLAIN TEXT"}')
            output.append(line)
        elif args.decrypt and is_protected(value):
            output.append(f'{key}={unprotect_value(value)}')
            changed.append(key)
        elif not args.decrypt and key in SENSITIVE_KEYS and not is_protected(value):
            output.append(f'{key}={protect_value(value)}')
            changed.append(key)
        else:
            output.append(line)

    if args.check:
        return

    with open(args.env_file, 'w', encoding='utf-8', newline='\n') as env_file:
        env_file.write('\n'.join(output) + '\n')

    action = 'Decrypted' if args.decrypt else 'Encrypted'
    print(f'{action}: {", ".join(changed) if changed else "nothing to change"}')


if __name__ == '__main__':
    main()
