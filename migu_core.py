"""加密核心加载器：导入时解密 migu_core.enc 到临时目录并挂到 sys.path

用法：
    import migu_core
    migu_core.load()          # 解密并返回目录
    import migu_play           # 之后即可正常导入

依赖：MIGU_CORE_KEY 环境变量；cryptography。若明文文件已存在（本地开发），
则直接使用明文，不解密。
"""
import atexit
import hashlib
import importlib
import os
import shutil
import sys
import tempfile
import zipfile

MAGIC = b'MIGUC01'
ITER = 200_000
HERE = os.path.dirname(os.path.abspath(__file__))
ENC = os.path.join(HERE, 'migu_core.enc')

_state = {'dir': None}


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITER, 32)


def _cleanup():
    d = _state.get('dir')
    if d and os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    _state['dir'] = None


def load(force: bool = False) -> str:
    """解密核心包，返回可导入的目录路径。"""
    if _state['dir'] and not force:
        return _state['dir']

    if not os.path.isfile(ENC):
        if os.path.isfile(os.path.join(HERE, 'migu_play.py')):
            _state['dir'] = HERE          # 本地明文模式
            return HERE
        raise RuntimeError('找不到 migu_core.enc，也没有明文文件')

    pwd = os.environ.get('MIGU_CORE_KEY')
    if not pwd:
        raise RuntimeError('需要环境变量 MIGU_CORE_KEY 才能解密核心包')

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    with open(ENC, 'rb') as f:
        blob = f.read()
    if not blob.startswith(MAGIC):
        raise RuntimeError('migu_core.enc 格式不对')

    p = len(MAGIC)
    salt, nonce, ct = blob[p:p + 16], blob[p + 16:p + 28], blob[p + 28:]
    data = AESGCM(_derive(pwd, salt)).decrypt(nonce, ct, MAGIC)

    d = tempfile.mkdtemp(prefix='migu_core_')
    with zipfile.ZipFile(__import__('io').BytesIO(data)) as z:
        z.extractall(d)
    atexit.register(_cleanup)
    _state['dir'] = d
    if d not in sys.path:
        sys.path.insert(0, d)
    return d


def run_module(name: str, argv=None):
    """Load encrypted/source-less core and execute module.main(argv)."""
    load(force=True)
    module = importlib.import_module(name)
    if not hasattr(module, 'main'):
        raise RuntimeError('模块没有 main(): ' + name)
    old_argv = sys.argv[:]
    try:
        sys.argv = [name] + list(argv or [])
        result = module.main()
        return int(result or 0)
    finally:
        sys.argv = old_argv


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == 'run':
        raise SystemExit(run_module(sys.argv[2], sys.argv[3:]))
    d = load(force=True)
    print('核心已就绪:', d)


if __name__ == '__main__':
    main()
