"""LIBERO 路径解析（唯一入口，避免脚本里散落绝对路径）。

解析顺序：
  1. $AGENT_LIBERO_ROOT
  2. <repo>/third_party/LIBERO        （bootstrap_env.sh 装在这里）
  3. /home/wei/work/g05/LIBERO-master （开发机历史路径，仅向后兼容）

另外：LIBERO 用 $LIBERO_CONFIG_PATH/config.yaml 解析 bddl/init/assets 目录，默认是
用户级的 ~/.libero —— 一台机器上装过两个 LIBERO 时会静默写到"先装的那个"里。
只要仓库内有 third_party/libero_config/config.yaml，就在这里把它指过去。
"""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

DEV_LIBERO = pathlib.Path("/home/wei/work/g05/LIBERO-master")
PROJ_CONFIG = ROOT / "third_party" / "libero_config"


def _valid(p) -> bool:
    p = pathlib.Path(p)
    return (p / "libero" / "libero").is_dir()


def libero_config_path() -> pathlib.Path:
    return PROJ_CONFIG


def libero_root() -> pathlib.Path:
    env = os.environ.get("AGENT_LIBERO_ROOT")
    if env and _valid(env):
        root = pathlib.Path(env)
    else:
        root = None
        for cand in (ROOT / "third_party" / "LIBERO", DEV_LIBERO):
            if _valid(cand):
                root = cand
                break
        if root is None:
            root = ROOT / "third_party" / "LIBERO"

    # 项目内有自己的 LIBERO 路径配置时优先使用（目录隔离，避免写错树）
    if (PROJ_CONFIG / "config.yaml").is_file():
        os.environ["LIBERO_CONFIG_PATH"] = str(PROJ_CONFIG)
    return pathlib.Path(root)
