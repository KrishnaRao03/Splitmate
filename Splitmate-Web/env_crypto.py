"""Keep secrets in .env encrypted at rest with Windows DPAPI.

A protected value looks like ``MAIL_PASSWORD=dpapi:<base64>``. Only the same
Windows user on the same machine can decrypt it, so a copied .env is useless
elsewhere. config.py decrypts these values at start-up. Plain values and real
environment variables keep working, which is what servers, CI and macOS/Linux use.
"""
import base64
import ctypes
import sys

PREFIX = 'dpapi:'
# Values scripts/protect_env.py encrypts by default.
SENSITIVE_KEYS = (
    'SECRET_KEY',
    'FIELD_ENCRYPTION_KEY',
    'DATABASE_URL',
    'MAIL_PASSWORD',
    'GEMINI_API_KEY',
    'STRIPE_SECRET_KEY',
)
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [('cbData', ctypes.c_uint32), ('pbData', ctypes.c_void_p)]


def is_protected(value):
    return value.startswith(PREFIX)


def _dpapi(function_name, data):
    if sys.platform != 'win32':
        raise RuntimeError(
            'This .env has DPAPI-encrypted values, which only Windows can read. '
            'Set those variables in the environment instead.'
        )

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = _DataBlob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
    blob_out = _DataBlob()
    ok = getattr(crypt32, function_name)(
        ctypes.byref(blob_in), None, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def protect_value(value):
    encrypted = _dpapi('CryptProtectData', value.encode('utf-8'))
    return PREFIX + base64.b64encode(encrypted).decode('ascii')


def unprotect_value(value):
    try:
        encrypted = base64.b64decode(value[len(PREFIX):])
        return _dpapi('CryptUnprotectData', encrypted).decode('utf-8')
    except OSError as exc:
        raise RuntimeError(
            'Could not decrypt a value in .env. It was encrypted by a different Windows user '
            'or machine. Restore the original value and run scripts/protect_env.py again.'
        ) from exc
