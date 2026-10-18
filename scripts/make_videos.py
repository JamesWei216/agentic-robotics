#!/usr/bin/env python3
"""Render a handful of demo videos (successes + known failures) for the report.

    python scripts/make_videos.py                 # default set
    python scripts/make_videos.py t0:1000 t6:1006 # explicit task:seed pairs

Videos land in runs/videos/<tag>_<t>_s<seed>/episode.mp4 and a copy is collected
into reports/videos/.
"""
import json
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import executor  # noqa: E402

DEFAULT = ["0:1000", "1:1000", "5:1000", "6:1000", "6:1006", "9:1003"]
SUITE = os.environ.get("VIDEO_SUITE", "libero_bolt_v2")
os.environ["AGENT_SUITE"] = SUITE   # executor picks the suite up from the env
CODE = os.environ.get("VIDEO_CODE", "")
OUT = ROOT / "reports" / "videos"


def main():
    pairs = sys.argv[1:] or DEFAULT
    code = pathlib.Path(CODE) if CODE else None
    if code is None:
        cands = sorted((ROOT / "runs").glob("*v2_primary*/task.py"))
        if not cands:
            cands = sorted((ROOT / "runs").glob("*_v2_final2/task.py"))
        code = cands[-1]
    print(f"suite={SUITE} code={code}")
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for pair in pairs:
        t, s = pair.split(":")
        t, s = int(t), int(s)
        run_dir = ROOT / "runs" / "videos" / f"{SUITE}_t{t}_s{s}"
        res = executor.run_episode(code, task_idx=t, seed=s, run_dir=run_dir,
                                   render=True)
        print(f"  t{t} s{s}: success={res.success} steps={res.steps} "
              f"{res.duration_s}s video={res.video}")
        if res.video and pathlib.Path(res.video).exists():
            dst = OUT / f"{SUITE}_t{t}_s{s}_{'ok' if res.success else 'fail'}.mp4"
            shutil.copy2(res.video, dst)
            made.append((dst.name, dst.stat().st_size // 1024))
    print("\ncollected:")
    for name, kb in made:
        print(f"  {name}  {kb} KB")
    (OUT / "README.md").write_text(
        "# 演示视频\n\n"
        f"套件 `{SUITE}`，代码 `{code.relative_to(ROOT)}`，每条 episode 独立进程 + 逐原语 trace。\n\n"
        + "\n".join(f"- `{n}`（{kb} KB）" for n, kb in made) + "\n")


if __name__ == "__main__":
    main()
