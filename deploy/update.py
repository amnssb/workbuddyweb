#!/usr/bin/env python3
"""一键更新的后台执行器（由 server/services/updater.py 脱离父进程拉起）。

单仓库模型：管理端后端（server/）、上游 Go 网关（upstream/）与前端静态产物
（web/out）都在同一个仓库里。因此两条更新路径都「根据本仓库走」：

  · update_manager：下载本仓库 Release 里的更新包（tar.gz + .sig），
    **验签通过后**替换 server/、web/out/、.version 与 CHANGELOG，再重启服务；
  · update_upstream：在上游目录（= 仓库工作区）git 拉取本仓库最新代码
    （或固定版本 WB_UPSTREAM_REF），再 docker compose 重建容器。

进度写入状态文件（WB_UPDATE_STATUS），管理端轮询展示；本脚本不接受任何
客户端传入的命令或路径，目标固定为 manager / upstream / both。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── 路径与常量（全部来自环境变量，由管理端注入）─────────────
INSTALL_DIR = Path(os.environ.get('WB_INSTALL_DIR') or Path(__file__).resolve().parent.parent)
DATA_DIR = Path(os.environ.get('WB_DATA_DIR') or INSTALL_DIR / 'data')
UPSTREAM_DIR = Path(os.environ.get('WB_UPSTREAM_DIR') or DATA_DIR)
STATUS_FILE = Path(os.environ.get('WB_UPDATE_STATUS') or DATA_DIR / 'update-status.json')
SERVICE_NAME = os.environ.get('WB_SERVICE_NAME', 'workbuddy-web')
MANAGER_REPO = os.environ.get('WB_MANAGER_REPO') or 'amnssb/workbuddyweb'

# 发布包签名信任锚：私钥离线保管（不进仓库、不进 CI）。占位值 = 未配置，
# 此时拒绝一切自动更新（默认安全）。deploy/release-signing-key.pub 必须与
# 内嵌值一致（有测试钉死）。
RELEASE_PUBKEY = os.environ.get('WB_RELEASE_PUBKEY') or (
    'ssh-ed25519 AAAA_REPLACE_ME_WITH_YOUR_REAL_PUBLIC_KEY release-signing'
)
RELEASE_SIGNER_ID = os.environ.get('WB_RELEASE_SIGNER') or 'release-signing'
# 导入时固化（测试与部署都按「设环境 → 导入」的口径使用）
SKIP_SIGNATURE = (os.environ.get('WB_SKIP_SIGNATURE') or '').strip() == '1'
_PLACEHOLDER_MARK = 'AAAA_REPLACE_ME_WITH_YOUR_REAL_PUBLIC_KEY'

# 更新包体积下限：小于它多半是把 404/错误页当成了包
_MIN_PKG_BYTES = 100_000


# ── 基础工具 ─────────────────────────────────────────────
def run(cmd: list, cwd=None, rep=None, check: bool = True, timeout: int = 1800) -> tuple:
    """执行命令，返回 (returncode, 输出文本)。

    check=True 时非 0 退出会抛 RuntimeError，并附上 _diagnose_build_failure
    的人话诊断（docker 构建失败时原始报错几乎不可读）。
    """
    if rep is not None:
        rep.log(f'$ {" ".join(cmd)}')
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                              capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        if check:
            raise RuntimeError(f'命令不存在: {exc}') from exc
        return 127, str(exc)
    out = (proc.stdout or '') + (proc.stderr or '')
    if proc.returncode != 0 and check:
        hint = _diagnose_build_failure(out)
        raise RuntimeError(
            f'命令失败（exit {proc.returncode}）: {" ".join(cmd)}\n{out[-2000:]}'
            + (f'\n诊断：{hint}' if hint else '')
        )
    return proc.returncode, out


def http_json(url: str, timeout: int = 20) -> object:
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'workbuddy-manager-updater',
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def download(url: str, dest: Path, rep) -> None:
    rep.log(f'下载 {url}')
    with urllib.request.urlopen(url, timeout=120) as resp, open(dest, 'wb') as fh:
        shutil.copyfileobj(resp, fh)
    size = dest.stat().st_size
    if size < _MIN_PKG_BYTES and dest.suffix in ('.gz', '.tgz'):
        dest.unlink(missing_ok=True)
        raise RuntimeError(f'下载结果异常偏小（{size} 字节），疑似错误页，已放弃')


def in_container() -> bool:
    """运行形态判定：显式配置优先，否则探测（与管理端 updater.py 同口径）。"""
    mode = (os.environ.get('WB_RUN_MODE') or 'auto').strip().lower()
    if mode in ('docker', 'container'):
        return True
    if mode in ('systemd', 'host'):
        return False
    if Path('/.dockerenv').exists():
        return True
    try:
        cg = Path('/proc/1/cgroup').read_text(encoding='utf-8')
        if any(k in cg for k in ('docker', 'containerd', 'kubepods', 'podman')):
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def restart_service(rep) -> None:
    """宿主形态走 systemctl；容器形态不执行任何命令（交给编排层）。"""
    if in_container():
        rep.log('容器形态：服务重启由编排层（compose restart 策略）负责')
        return
    rep.log(f'重启服务 {SERVICE_NAME}')
    run(['systemctl', 'restart', SERVICE_NAME], rep=rep, check=False)


def _exit_for_restart(rep) -> None:
    """容器形态：向 PID 1 发 SIGTERM，让编排层用新代码拉起整个容器。

    只结束更新进程是不够的——管理端主进程仍在跑旧代码，界面还是旧版。
    容器无法「重启自己」，但结束 PID 1 后 compose 的 restart 策略会重建。
    """
    rep.log('容器形态：结束容器以应用新代码（compose 会自动拉起）')
    os.kill(1, signal.SIGTERM)
    time.sleep(5)


# ── 签名校验（供应链防护）─────────────────────────────────
def check_signature(pkg: Path, sig: Path, rep) -> bool:
    """用 ssh-keygen 校验发布包签名。失败一律抛 RuntimeError，绝不静默放行。"""
    if SKIP_SIGNATURE:
        rep.log('WB_SKIP_SIGNATURE=1：跳过签名校验（紧急逃生门，请事后核查发布来源）', 'warn')
        rep.set_signature('skipped', 'WB_SKIP_SIGNATURE=1')
        return True
    if _PLACEHOLDER_MARK in RELEASE_PUBKEY:
        raise RuntimeError(
            '公钥未配置：RELEASE_PUBKEY 仍是占位值，拒绝自动更新。'
            '请配置 WB_RELEASE_PUBKEY 或更新 deploy/release-signing-key.pub。'
        )
    if not sig.is_file():
        raise RuntimeError('没有可用的签名文件，拒绝安装（不能把「没签名」当通过）')

    allowed = sig.with_suffix('.allowed_signers')
    allowed.write_text(f'{RELEASE_SIGNER_ID} {RELEASE_PUBKEY}\n', encoding='utf-8')
    try:
        with open(pkg, 'rb') as msg:
            proc = subprocess.run(
                ['ssh-keygen', '-Y', 'verify', '-f', str(allowed),
                 '-I', RELEASE_SIGNER_ID, '-n', 'file', '-s', str(sig)],
                stdin=msg, capture_output=True, text=True, timeout=120,
            )
    except FileNotFoundError as exc:
        raise RuntimeError(f'签名校验失败：ssh-keygen 不可用（{exc}）') from exc
    finally:
        allowed.unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f'签名校验失败，中止更新：{(proc.stderr or proc.stdout or "").strip()[:300]}'
        )
    rep.log('签名校验通过')
    rep.set_signature('verified', RELEASE_SIGNER_ID)
    return True


def verify_release_signature(pkg: Path, sig_url: str, rep) -> None:
    """下载签名文件到包旁边并验签。验签必须在解压之前完成。"""
    rep.log('校验发布包签名')
    sig = Path(str(pkg) + '.sig')
    if not sig_url:
        raise RuntimeError('没有可用的签名文件，拒绝安装')
    try:
        rep.log(f'下载签名文件 {sig_url}')
        download_any(sig_url, sig)
    except Exception as exc:  # noqa: BLE001
        sig.unlink(missing_ok=True)
        raise RuntimeError(f'没有可用的签名文件（下载失败：{exc}），拒绝安装') from exc
    check_signature(pkg, sig, rep)


def download_any(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as resp, open(dest, 'wb') as fh:
        shutil.copyfileobj(resp, fh)


def _safe_extract(pkg: Path, dest: Path) -> Path:
    """解压并防路径穿越；返回包内唯一顶层目录。"""
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(pkg, 'r:gz') as tf:
        for member in tf.getmembers():
            name = member.name
            if name.startswith('/') or '..' in Path(name).parts:
                raise RuntimeError(f'发布包含非法路径：{name}')
        tf.extractall(dest)  # noqa: S202 成员路径已逐一校验
    tops = [p for p in dest.iterdir() if p.is_dir()]
    if len(tops) != 1:
        raise RuntimeError(f'发布包结构异常（顶层目录 {len(tops)} 个）')
    return tops[0]


# ── 管理端更新 ───────────────────────────────────────────
def update_manager(rep) -> None:
    rep.step('更新管理端')
    rel = http_json(f'https://api.github.com/repos/{MANAGER_REPO}/releases/latest')
    tag = str((rel or {}).get('tag_name') or '').strip()
    if not tag:
        raise RuntimeError('未找到可用 Release（仓库可能还没发过版）')
    rep.set_target_version(tag)
    rep.log(f'目标版本 {tag}')

    assets = (rel or {}).get('assets') or []
    pkg_asset = next((a for a in assets
                      if str(a.get('name') or '').endswith('.tar.gz')), None)
    if pkg_asset is None:
        raise RuntimeError('Release 里没有更新包资产（.tar.gz）')
    sig_url = next((str(a.get('browser_download_url') or '') for a in assets
                    if str(a.get('name') or '') == str(pkg_asset.get('name') or '') + '.sig'), '')

    work = DATA_DIR / 'update-tmp'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    pkg = work / str(pkg_asset.get('name') or 'release.tar.gz')
    download(str(pkg_asset.get('browser_download_url') or ''), pkg, rep)

    # 先验签、后解压：确认「包是我们签的」，再谈包里的内容
    verify_release_signature(pkg, sig_url, rep)
    new_root = _safe_extract(pkg, work / 'extracted')

    # 备份当前安装（出问题能回退），含 deploy/ 以便对照
    backup = INSTALL_DIR / f'backup-{time.strftime("%Y%m%d-%H%M%S")}'
    for part in ('server', 'web', 'deploy'):
        src = INSTALL_DIR / part
        if src.is_dir():
            shutil.copytree(src, backup / part)
    rep.log(f'已备份当前安装到 {backup}')

    for part in ('server', 'web/out'):
        src = new_root / part
        dst = INSTALL_DIR / part
        if src.is_dir():
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
    for fname in ('.version', 'CHANGELOG.md'):
        src = new_root / fname
        if src.is_file():
            shutil.copyfile(src, INSTALL_DIR / fname)

    req = INSTALL_DIR / 'server' / 'requirements.txt'
    if req.is_file() and req.read_text(encoding='utf-8').strip():
        rep.log('安装 Python 依赖')
        run([sys.executable or 'python3', '-m', 'pip', 'install',
             '--no-cache-dir', '-r', str(req)], rep=rep)

    # deploy/ 是验签信任锚：默认随包同步（包已验签，与 server/ 同一性质），
    # WB_SYNC_DEPLOY=0 可关闭（手工维护者的退路）。不整体 copytree，逐文件分类。
    pkg_deploy = new_root / 'deploy'
    if pkg_deploy.is_dir():
        added, modified = [], []
        for src in sorted(pkg_deploy.rglob('*')):
            if not src.is_file():
                continue
            rel_name = str(src.relative_to(pkg_deploy))
            dst = INSTALL_DIR / 'deploy' / rel_name
            if not dst.is_file():
                added.append(rel_name)
            elif dst.read_bytes() != src.read_bytes():
                modified.append(rel_name)
        if added or modified:
            if _deploy_sync_enabled():
                _sync_deploy(pkg_deploy, INSTALL_DIR, backup, rep)
                rep.log('deploy/ 已同步到包内版本')
            else:
                rep.log(f'已跳过同步 deploy/（WB_SYNC_DEPLOY=0）', 'warn')
                if modified:
                    rep.log(f'修改（未覆盖）：{", ".join(modified)}', 'warn')
                if added:
                    rep.log(f'新增（未覆盖）：{", ".join(added)}')
                _explain_deploy_risk(rep, modified, added,
                                     INSTALL_DIR / 'deploy', backup)

    shutil.rmtree(work, ignore_errors=True)
    _clear_version_cache()
    rep.log(f'管理端已更新到 {tag}，重启服务以生效')
    if in_container():
        _exit_for_restart(rep)
    else:
        restart_service(rep)
    rep.finish(True)


def _deploy_sync_enabled() -> bool:
    """只有显式 0 表示关闭；缺省/其它值都按同步处理。调用时读 env。"""
    return (os.environ.get('WB_SYNC_DEPLOY') or '').strip() != '0'


def _sync_deploy(pkg_deploy: Path, install: Path, backup: Path, rep) -> tuple:
    """把验签过的包内 deploy/ 逐文件同步进安装目录，覆盖前备份。返回 (added, modified)。"""
    added, modified = [], []
    for src in sorted(pkg_deploy.rglob('*')):
        if not src.is_file():
            continue
        rel = src.relative_to(pkg_deploy)
        dst = install / 'deploy' / rel
        if dst.is_file():
            if dst.read_bytes() == src.read_bytes():
                continue
            modified.append(str(rel))
            bak = backup / 'deploy' / rel
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dst, bak)
        else:
            added.append(str(rel))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    rep.log('如需保持本地 deploy/ 不变，可设 WB_SYNC_DEPLOY=0')
    return added, modified


def _explain_deploy_risk(rep, modified: list, added: list, here: Path,
                         backup: Path | None = None) -> None:
    """deploy/ 差异提示分清轻重：新增无害、普通文件按需、信任锚必须人工确认。"""
    anchors = [m for m in modified
               if Path(m).name in ('update.py', 'release-signing-key.pub')]
    if anchors:
        rep.log('包内含验签相关文件（update.py / 公钥）的改动：跳过同步后请人工确认'
                f'差异再决定是否覆盖——这是供应链防护的最后一关：{", ".join(anchors)}', 'warn')
    elif modified:
        rep.log(f'deploy/ 有修改的文件，看过差异后可从包内按需覆盖：{", ".join(modified)}')
    if added:
        rep.log(f'以下文件为包内仅新增，不影响本次更新，可以不处理：{", ".join(added)}')
    if modified or added:
        rep.log('自动同步 deploy/ 随包更新请保持默认（WB_SYNC_DEPLOY=1 或缺省）；'
                '保持本地不变请设 WB_SYNC_DEPLOY=0')
    if backup is not None and any(Path(m).name == 'update.py' for m in modified):
        rep.log('不同步意味着更新器本身会停留在旧版本，以后仍用旧逻辑执行更新；'
                f'旧文件已备份到 {backup}', 'warn')


# ── 上游更新（git 拉取本仓库 + compose 重建）──────────────
def _read_upstream_ref() -> str:
    """固定上游版本：环境变量优先，其次状态目录里的文件；空 = 跟随分支。"""
    ref = (os.environ.get('WB_UPSTREAM_REF') or '').strip()
    if ref:
        return ref
    ref_file = os.environ.get('WB_UPSTREAM_REF_FILE') or ''
    if ref_file:
        try:
            return Path(ref_file).read_text(encoding='utf-8').strip()
        except Exception:  # noqa: BLE001
            return ''
    return ''


def _missing_copy_sources() -> list:
    """构建前预检：Dockerfile 里 COPY 了仓库中不存在的文件（真实事故形态）。"""
    df = UPSTREAM_DIR / 'Dockerfile'
    if not df.is_file():
        return []
    missing: list = []
    try:
        lines = df.read_text(encoding='utf-8', errors='replace').splitlines()
    except Exception:  # noqa: BLE001
        return []
    for line in lines:
        parts = line.strip().split()
        if not parts or parts[0].upper() != 'COPY':
            continue
        if '--from=' in line.lower():
            continue
        # 去掉 flag（--chown= 等），剩下的是 源... 目标
        args = [p for p in parts[1:] if not p.startswith('--')]
        if len(args) < 2:
            continue
        for src in args[:-1]:
            if '*' in src or src.startswith(('http://', 'https://')):
                continue
            if not (UPSTREAM_DIR / src).exists():
                missing.append(src)
    return missing


def _diagnose_build_failure(out: str) -> str:
    """把 docker 构建报错归纳成人话；认不出的返回空串。"""
    low = (out or '').lower()
    if 'failed to calculate checksum' in low and 'not found' in low:
        return ('上游 Dockerfile 引用了不存在的文件——通常是上游这个提交自身有问题，'
                '可用「固定上游版本」回退到上一个可用提交')
    if 'no space left on device' in low:
        return '磁盘空间不足，清理 docker 占用（docker system prune）后重试'
    if 'i/o timeout' in low or 'dial tcp' in low:
        return '网络问题（拉取依赖/镜像超时），可配置构建加速参数后重试'
    if 'permission denied' in low:
        return '权限不足，确认当前用户可操作 docker（docker 组或 root）'
    return ''


def _has_compose_v2() -> bool:
    try:
        return subprocess.run(['docker', 'compose', 'version'],
                              capture_output=True, timeout=10).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _has_compose_v1() -> bool:
    try:
        return subprocess.run(['docker-compose', '--version'],
                              capture_output=True, timeout=10).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _compose_plugin_paths() -> list:
    """compose v2 插件的常见安装位置（仅用于诊断输出，绝不能抛）。"""
    candidates = [
        '/usr/lib/docker/cli-plugins/docker-compose',
        '/usr/local/lib/docker/cli-plugins/docker-compose',
        '/usr/libexec/docker/cli-plugins/docker-compose',
    ]
    try:
        candidates.append(str(Path.home() / '.docker' / 'cli-plugins' / 'docker-compose'))
    except Exception:  # noqa: BLE001 某些容器里 uid 没有 passwd 条目
        pass
    out: list = []
    for p in candidates:
        try:
            if Path(p).is_file():
                out.append(p)
        except Exception:  # noqa: BLE001
            continue
    return out


def _compose_cmd(rep=None) -> list | None:
    """选 compose 命令：v2 插件优先，退回 v1；都没有返回 None（绝不硬跑）。"""
    v2, v1 = _has_compose_v2(), _has_compose_v1()
    msg = f'compose 探测：docker compose={"可用" if v2 else "不可用"}，docker-compose={"可用" if v1 else "不可用"}'
    if rep is not None:
        rep.log(msg)
    if v2:
        return ['docker', 'compose']
    if v1:
        return ['docker-compose']
    if rep is not None:
        paths = _compose_plugin_paths()
        if paths:
            rep.log(f'已发现的 compose 插件：{", ".join(paths)}')
        else:
            rep.log('未发现 compose 插件（/usr/local/lib/docker/cli-plugins/ 等位置均无）')
    return None


def _port_converged(text: str) -> str:
    """把上游 compose 的公网端口绑定收敛到本机（纯文本替换，不动其它配置）。"""
    return text.replace('- "7863:7863"', '- "127.0.0.1:7863:7863"')


def _compose_looks_customized(rep) -> bool:
    """用户是否改过 docker-compose.yml（我们自己做的端口收敛不算定制）。"""
    compose_file = UPSTREAM_DIR / 'docker-compose.yml'
    if not compose_file.is_file():
        return False
    rc, head_text = run(['git', 'show', 'HEAD:docker-compose.yml'],
                        cwd=UPSTREAM_DIR, check=False)
    if rc != 0 or not head_text:
        return False
    try:
        current = compose_file.read_text(encoding='utf-8')
    except Exception:  # noqa: BLE001
        return False
    customized = current != _port_converged(head_text)
    if customized:
        rep.log('检测到 docker-compose.yml 有本地定制，更新后会原样恢复')
    return customized


def wait_health(rep, timeout: int = 60) -> bool:
    base = (os.environ.get('WB2API_BASE') or 'http://127.0.0.1:7863').rstrip('/')
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'{base}/healthz', timeout=5) as resp:
                if resp.status in (200, 503):
                    rep.log('上游健康检查通过')
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    rep.log('上游健康检查未通过（可能仍在启动，稍后到控制台确认）', 'warn')
    return False


def _clear_version_cache() -> None:
    """更新后清除版本检测缓存，避免界面拿旧 sha 继续提示「有更新」。"""
    try:
        (DATA_DIR / 'version-check.json').unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


def update_upstream(rep) -> None:
    rep.step('更新上游')
    if not (UPSTREAM_DIR / '.git').exists():
        raise RuntimeError(
            f'上游目录 {UPSTREAM_DIR} 不是 git 仓库（容器部署时代码打进镜像）。'
            '请在宿主机仓库目录执行：git pull && docker compose up -d --build'
        )

    missing = _missing_copy_sources()
    if missing:
        raise RuntimeError(
            f'上游 Dockerfile 引用了不存在的文件：{", ".join(missing)}。'
            '这通常是上游提交自身的问题，可用「固定上游版本」回退后再更新'
        )

    customized = _compose_looks_customized(rep)
    saved_custom = ''
    if customized:
        compose_file = UPSTREAM_DIR / 'docker-compose.yml'
        saved_custom = compose_file.read_text(encoding='utf-8')
        rc, diff = run(['git', 'diff'], cwd=UPSTREAM_DIR, check=False)
        if rc == 0 and diff.strip():
            patch = DATA_DIR / 'compose-custom.patch'
            patch.write_text(diff, encoding='utf-8')
            rep.log(f'本地定制已备份到 {patch}')

    run(['git', 'checkout', '--', '.'], cwd=UPSTREAM_DIR, rep=rep)
    run(['git', 'fetch', 'origin', '--tags'], cwd=UPSTREAM_DIR, rep=rep)

    ref = _read_upstream_ref()
    if ref:
        rep.log(f'检出固定版本 {ref}')
        run(['git', 'checkout', ref], cwd=UPSTREAM_DIR, rep=rep)
    else:
        _, branch = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                        cwd=UPSTREAM_DIR, check=False)
        branch = (branch or '').strip() or 'main'
        run(['git', 'reset', '--hard', f'origin/{branch}'], cwd=UPSTREAM_DIR, rep=rep)
    _, sha = run(['git', 'rev-parse', 'HEAD'], cwd=UPSTREAM_DIR, check=False)
    rep.log(f'上游代码已更新到 {(sha or "").strip()[:8]}')

    compose = _compose_cmd(rep)
    if compose is None:
        raise RuntimeError(
            'docker compose 不可用：环境里既没有 docker compose（v2 插件）也没有 '
            'docker-compose（v1）。请在镜像/宿主机安装 compose 插件（见 Dockerfile），'
            '或在宿主机仓库目录手动执行 docker compose up -d --build 完成更新'
        )
    run(compose + ['up', '-d', '--build'], cwd=UPSTREAM_DIR, rep=rep)
    wait_health(rep)

    compose_file = UPSTREAM_DIR / 'docker-compose.yml'
    if compose_file.is_file():
        base_text = saved_custom or compose_file.read_text(encoding='utf-8')
        converged = _port_converged(base_text)
        if compose_file.read_text(encoding='utf-8') != converged:
            compose_file.write_text(converged, encoding='utf-8')
            rep.log('已恢复本地定制并重新收敛端口到 127.0.0.1')

    _clear_version_cache()
    rep.log('上游更新完成')


# ── 进度上报 ─────────────────────────────────────────────
class Reporter:
    """把进度实时落盘成状态文件，管理端轮询展示。"""

    def __init__(self) -> None:
        self.state: dict = {
            'running': True,
            'ok': None,
            'step': '',
            'logs': [],
            'pid': os.getpid(),
            'started_at': int(time.time()),
        }
        self._flush()

    def log(self, msg: str, level: str = 'info') -> None:
        self.state['logs'].append({'t': int(time.time()), 'level': level, 'text': msg})
        self.state['logs'] = self.state['logs'][-200:]
        self.state['step'] = msg
        self._flush()

    def step(self, name: str) -> None:
        self.log(f'== {name} ==')

    def set_target_version(self, tag: str) -> None:
        self.state['target_version'] = str(tag or '').strip().lstrip('vV')
        self._flush()

    def set_signature(self, status: str, detail: str = '') -> None:
        self.state['signature'] = {'status': status, 'detail': detail}
        self._flush()

    def finish(self, ok: bool) -> None:
        self.state['running'] = False
        self.state['ok'] = bool(ok)
        self.state['finished_at'] = int(time.time())
        self._flush()

    def _flush(self) -> None:
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = STATUS_FILE.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')
            tmp.replace(STATUS_FILE)
        except Exception:  # noqa: BLE001 状态落盘失败不能带崩更新本身
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', default='manager',
                    choices=('manager', 'upstream', 'both'))
    args = ap.parse_args()

    rep = Reporter()
    ok = True
    try:
        # 先上游、后管理端：管理端更新最后会重启服务/结束容器，必须放最后
        if args.target in ('upstream', 'both'):
            update_upstream(rep)
        if args.target in ('manager', 'both'):
            update_manager(rep)
    except Exception as exc:  # noqa: BLE001
        rep.log(f'更新失败：{exc}', 'error')
        ok = False
    # manager 成功路径里 finish 已调用（随后服务重启）；这里兜底
    if rep.state.get('running'):
        rep.finish(ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
