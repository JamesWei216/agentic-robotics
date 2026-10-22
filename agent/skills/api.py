"""Robot API — the primitive surface exposed to agent-generated task code.

Contract with the harness (environment variables):
    AGENT_SUITE       benchmark suite name           (default: libero_bolt)
    AGENT_TASK_IDX    task index inside the suite    (default: 0)
    AGENT_SEED        initial-state seed             (default: 1000)
    AGENT_RUN_DIR     where trace.jsonl / video go   (default: runs/_adhoc)
    AGENT_RENDER      1 -> capture an mp4            (default: 0)
    AGENT_CONFIRM_MODE  auto | manual | deny         (default: auto)

Generated code only ever sees this class. Every primitive:
  1. goes through the safety layer (workspace / travel / e-stop),
  2. goes through the confirmation gate when the action is gated,
  3. appends a structured event to the trace (stdout + trace.jsonl).
"""
from __future__ import annotations

import atexit
import json
import os
import pathlib
import sys
import time

import numpy as np

def _resolve_libero() -> str:
    """AGENT_LIBERO_ROOT → <repo>/third_party/LIBERO → 开发机历史路径。"""
    env = os.environ.get("AGENT_LIBERO_ROOT")
    repo = pathlib.Path(__file__).resolve().parents[2]
    for cand in ([pathlib.Path(env)] if env else []) + [
        repo / "third_party" / "LIBERO",
        pathlib.Path("/home/wei/work/g05/LIBERO-master"),
    ]:
        if (cand / "libero" / "libero").is_dir():
            return str(cand)
    return str(repo / "third_party" / "LIBERO")


LIBERO_ROOT = _resolve_libero()
if LIBERO_ROOT not in sys.path:
    sys.path.insert(0, LIBERO_ROOT)

# LIBERO 的 bddl/init/assets 目录由 $LIBERO_CONFIG_PATH/config.yaml 决定（默认是用户级的 ~/.libero，
# 一台机器上装过两个 LIBERO 时会静默写到“先装的那个”）。仓库内有 bootstrap 生成的配置就用它。
_pcfg = pathlib.Path(__file__).resolve().parents[2] / "third_party" / "libero_config"
if (_pcfg / "config.yaml").is_file():
    os.environ["LIBERO_CONFIG_PATH"] = str(_pcfg)

from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.confirm import ConfirmationDenied, gate  # noqa: E402
from agent.safety import Estop, Safety, SafetyViolation  # noqa: E402
from agent.skills.expert import EpisodeDone, Expert  # noqa: E402

GATED = {
    "first_motion": "解除使能 / 首次运动",
    "grasp_close": "夹爪闭合（抓取）",
    "release": "夹爪张开（释放物料）",
    "long_travel": "长距离移动",
}

BIN_PREFIX = "parts_bin"
PERCEPTION_MODE = os.environ.get("AGENT_PERCEPTION", "privileged").lower()


def _scene_objects(env) -> list[str]:
    """All movable object names the current episode actually has."""
    return [n for n in env.env.obj_body_id]


class Robot:
    # ------------------------------------------------------------------ setup
    def __init__(self, env, expert: Expert, run_dir: pathlib.Path, render: bool = False):
        self.env = env
        self.u = env.env
        self.ex = expert
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.run_dir / "trace.jsonl"
        self.safety = Safety()
        self.gate = gate()
        self.steps = 0
        self.events = 0
        self._armed = False
        self._frames = []
        self._render = render
        self._video_every = int(os.environ.get("AGENT_VIDEO_EVERY", "2"))
        self._home = (self.ex.ee()[0].copy(), self.ex.ee()[1].copy())

        self.ex.recorder = self._record          # step counting always on
        self.mission = self._load_mission()
        self._closed = False
        self._success = None
        atexit.register(self.close)              # generated code may forget to

    @classmethod
    def from_env(cls) -> "Robot":
        suite_name = os.environ.get("AGENT_SUITE", "libero_bolt")
        task_idx = int(os.environ.get("AGENT_TASK_IDX", "0"))
        seed = int(os.environ.get("AGENT_SEED", "1000"))
        run_dir = pathlib.Path(os.environ.get("AGENT_RUN_DIR", "runs/_adhoc"))
        render = os.environ.get("AGENT_RENDER", "0") == "1"

        suite = get_benchmark_dict()[suite_name]()
        task = suite.get_task(task_idx)
        bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file
        # Protocol: the step budget scales with the number of required placements,
        # so a two-object task is not judged against a one-object horizon.
        n_items = max(1, len(cls._mission_from_env()))
        horizon = 400 + 800 * n_items
        # vision mode needs the depth buffer; everything else is unchanged
        # LIBERO's env.seed() seeds the simulator but NOT the global numpy RNG that
        # ObjectPositionSampler uses for the initial layout. Without this line the
        # same (task, seed) gives different object placements in different
        # processes -- measured: one of five fresh processes on v2 t2 seed 1004
        # raised RandomizationError, and the sampled bolt positions differed. With
        # it, five processes agree exactly. Seeded *before* the env is built so the
        # probe scripts (which seed first) reproduce the agent's layouts exactly.
        np.random.seed(seed)
        env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                                 horizon=horizon,
                                 camera_depths=(PERCEPTION_MODE == "vision"))
        env.seed(seed)
        env.reset()
        robot = cls(env, Expert(env), run_dir, render=render)
        robot.emit("episode_start", task=task.language, task_idx=task_idx,
                   seed=seed, bddl=str(bddl.name), perception=PERCEPTION_MODE)
        if PERCEPTION_MODE == "vision":
            robot._init_vision()
        return robot

    # ---------------------------------------------------------------- mission
    @staticmethod
    def _mission_from_env() -> list[dict]:
        raw = os.environ.get("AGENT_MISSION")
        if raw:
            return json.loads(raw)
        suite = os.environ.get("AGENT_SUITE", "libero_bolt")
        idx = os.environ.get("AGENT_TASK_IDX", "0")
        path = pathlib.Path(__file__).resolve().parents[2] / "config" / "missions.json"
        if path.exists():
            data = json.loads(path.read_text())
            return data.get(suite, {}).get(str(idx), [])
        return []

    def _load_mission(self) -> list[dict]:
        return self._mission_from_env()

    def todo(self) -> list[dict]:
        """What this episode requires: a list of {object, bin} pairs (copy)."""
        self.emit("todo", items=[f"{m['object']}->{m['bin']}" for m in self.mission])
        return [dict(m) for m in self.mission]

    # ------------------------------------------------------------------ trace
    def emit(self, event: str, **kw) -> None:
        self.events += 1
        rec = {"t": round(time.time(), 3), "event": event, "steps": self.steps_used, **kw}
        with self.trace_path.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("@@EV@@ " + json.dumps(rec, ensure_ascii=False), flush=True)

    def log(self, message: str, **kw) -> None:
        self.emit("log", message=str(message), **kw)

    @property
    def steps_used(self) -> int:
        return self.steps

    # -------------------------------------------------------------- perception
    def _init_vision(self) -> None:
        """Wire the RGB-D perception path into the primitives."""
        from agent.skills.perception import CameraModel
        self._cam = CameraModel(self.u.sim, "agentview", 256, 256)
        self._last_obs = None
        prev = self.ex.recorder

        def rec(obs, action):
            self._last_obs = obs
            if prev is not None:
                prev(obs, action)

        self.ex.recorder = rec
        self.ex.refresh_vision = self._perceive
        self.ex.last_obs = lambda: self._last_obs

    def _perceive(self):
        """Re-render one frame and update the detected scene. No GT poses."""
        from agent.skills.perception import perceive
        obs = self._last_obs
        if obs is None or "agentview_depth" not in obs:
            raise RuntimeError("vision perception: no depth frame available")
        scene = perceive(obs, self.u.sim, debug=False)
        self.ex.vision = scene
        return scene

    def scan(self, category: str = "bolt") -> list[dict]:
        """Return candidate objects of `category`.

        AGENT_PERCEPTION=vision  -> RGB-D segmentation + PCA (no ground truth)
        otherwise                -> simulator ground-truth poses (privileged)
        """
        self.safety.check_estop()
        if PERCEPTION_MODE == "vision":
            scene = self._perceive()
            found = []
            for item in scene.summary():
                kind = item["kind"]
                if category == "bolt" and not kind.startswith("bolt"):
                    continue
                if category not in ("all", "bolt") and kind != category:
                    continue
                found.append({"id": item["id"], "label": kind,
                              "pose": item["pos"], "source": "vision"})
            self.emit("scan", category=category, source="vision",
                      found=[f["id"] for f in found], detections=found)
            return found
        found = []
        for name in _scene_objects(self.env):
            if name not in self.u.obj_body_id:
                continue
            label = name.split("_1")[0]
            if category == "all":
                pass
            elif category == "bolt":
                if not label.startswith("bolt"):
                    continue
            elif label != category:
                continue
            found.append({"id": name, "label": label,
                          "pose": [round(float(v), 4) for v in self.ex.body_pos(name)],
                          "source": "privileged"})
        self.emit("scan", category=category, found=[f["id"] for f in found])
        return found

    # ----------------------------------------------------------- manipulation
    def _episode_done(self, primitive: str) -> bool:
        """True once the simulator reports `done` (goal predicate already holds).

        robosuite raises 'executing action in terminated episode' if you keep
        stepping afterwards -- that used to abort an episode *after* a successful
        placement, so trailing primitives (home/check) turned a win into a loss.
        All primitives now short-circuit instead.
        """
        if not getattr(self.u, "done", False):
            return False
        if self._success is None:
            self._success = bool(self.u._check_success())
        self.emit("skip_after_termination", primitive=primitive, success=self._success)
        return True

    def _arm_once(self) -> None:
        if self._armed:
            return
        self.gate.require("first_motion", {"mode": self.safety.mode})
        self.safety.audit({"event": "armed", "mode": self.safety.mode})
        self._armed = True

    def settle(self, steps: int = 30) -> None:
        steps = int(steps)
        self.safety.check_estop()
        if self._episode_done("settle"):
            return
        for _ in range(steps):
            try:
                self.ex.step(np.zeros(3), np.zeros(3), -1.0)
            except EpisodeDone:
                self._episode_done("settle")
                break
        self.emit("settle", n=steps)

    def _bolts(self) -> list[str]:
        if PERCEPTION_MODE == "vision":
            return [m["object"] for m in self.mission]
        return [n for n in _scene_objects(self.env) if n.startswith("bolt")]

    def _bins(self) -> list[str]:
        if PERCEPTION_MODE == "vision":
            return sorted({m["bin"] for m in self.mission})
        return [n for n in _scene_objects(self.env) if n.startswith(BIN_PREFIX)]

    def _check_object(self, name: str, *, allowed) -> None:
        if name not in allowed:
            raise ValueError(f"unknown object {name!r}; valid ids are {list(allowed)}")

    def pick(self, object: str) -> bool:
        self._check_object(object, allowed=self._bolts())
        if self._episode_done("pick"):
            return True
        self._arm_once()
        if getattr(self, "_just_placed", False):
            # Starting a grasp right after a release means approaching from over a
            # bin, a posture the OSC keeps saturating in (multi suite: the second /
            # third part of a batch failed to close on the part twice in a row).
            # Return to the known-good pose first.
            self._just_placed = False
            try:
                self.home()
            except Exception:
                pass
        if PERCEPTION_MODE == "vision":
            # closed loop: re-measure everything right before the grasp
            self._perceive()
        self.safety.guard_point(self.ex.grasp_point(object), label=f"grasp:{object}")
        self.gate.require("grasp_close", {"object": object})
        try:
            ok, _log = self.ex.grasp(object)
        except EpisodeDone:
            self.emit("pick", object=object, grasped=None, note="episode_terminated")
            return True
        self.emit("pick", object=object, grasped=bool(ok),
                  pos=[round(float(v), 4) for v in self.ex.ee()[0]])
        if not ok:
            raise RuntimeError(f"grasp failed: jaws closed on nothing ({object})")
        return True

    def place(self, object: str, box: str) -> bool:
        self._check_object(object, allowed=self._bolts())
        self._check_object(box, allowed=self._bins())
        if self._episode_done("place"):
            return bool(self._success)
        self._arm_once()
        self.gate.require("release", {"object": object, "target": box})
        try:
            ok, _log = self.ex.transfer(box)
        except EpisodeDone:
            ok = bool(self.u._check_success())
        if not ok and not self._episode_done("place"):
            # The part slipped out of the jaws or missed the cavity. Re-acquire and
            # try once more: the generated task code only retries on exceptions, so
            # a False return used to end the pair (vision t3 s1003: part lost on the
            # first climb, 171 steps wasted, no second attempt).
            # Budget guard: a re-grasp + transfer costs ~500-700 steps, so only do
            # it when the episode can still afford it (multi-part tasks share one
            # horizon across all parts).
            left = int(getattr(self.u, "horizon", 0)) - int(getattr(self.u, "timestep", 0))
            if left < 600:
                self.emit("place_retry_skipped", object=object, steps_left=left)
                self.emit("place", object=object, bin=box, success=False)
                return False
            self.emit("place_retry", object=object, bin=box, steps_left=left)
            try:
                if PERCEPTION_MODE == "vision":
                    self._perceive()
                self.ex.grasp(object)
                ok, _log = self.ex.transfer(box)
            except (RuntimeError, KeyError, EpisodeDone) as exc:
                self.emit("place_retry_failed", object=object, error=str(exc)[:160])
                ok = bool(self.u._check_success())
        self.emit("place", object=object, bin=box, success=bool(ok))
        self._just_placed = True
        return bool(ok)

    def pick_and_place(self, object: str, bin: str) -> bool:
        self._check_object(object, allowed=self._bolts())
        self._check_object(bin, allowed=self._bins())
        self.settle(30)
        self.pick(object)
        return self.place(object, bin)

    def home(self) -> None:
        if self._episode_done("home"):
            return
        pos, rot = self._home
        self.safety.guard_point(pos, label="home")
        try:
            self.ex.move_to(pos, rot, grip=-1.0, max_steps=120, speed=0.020)
            reached = [round(float(v), 4) for v in self.ex.ee()[0]]
        except EpisodeDone:
            self._episode_done("home")
            reached = None
        self.emit("home", pos=reached)

    # -------------------------------------------------------------- feedback
    def check(self) -> bool:
        ok = bool(self.u._check_success())
        self._success = ok
        self.emit("check", success=ok)
        return ok

    def confirm(self, action: str) -> bool:
        ok = self.gate.require(action, {"gated": GATED.get(action, action)})
        self.emit("confirm", action=action, approved=ok)
        return ok

    # ---------------------------------------------------------------- video
    def _record(self, obs, action) -> None:
        self.steps += 1
        self.safety.check_estop()
        if self._render and self.steps % self._video_every == 0:
            frame = obs.get("agentview_image")
            if frame is not None:
                self._frames.append(np.asarray(frame)[::-1].copy())

    def save_video(self, fps: int = 20) -> str | None:
        if not self._frames:
            return None
        import imageio.v2 as imageio  # vendored env has imageio
        path = self.run_dir / "episode.mp4"
        with imageio.get_writer(path, fps=max(1, fps // self._video_every), macro_block_size=1) as w:
            for f in self._frames:
                w.append_data(f)
        self.emit("video", path=str(path), frames=len(self._frames))
        return str(path)

    # ---------------------------------------------------------------- teardown
    def stats(self) -> dict:
        return {"steps": self.steps, "events": self.events,
                "confirmations": self.gate.count,
                "confirm_approved": self.gate.approved,
                "confirm_denied": self.gate.denied}

    def close(self) -> dict:
        if self._closed:
            return self.stats()
        self._closed = True
        stats = self.stats()
        if self._render:
            try:
                self.save_video()
            except Exception as e:  # noqa: BLE001 - video is best effort
                self.emit("video_error", error=f"{type(e).__name__}: {e}")
        self.emit("episode_end", success=self._success, **stats)
        try:
            (self.run_dir / "result.json").write_text(json.dumps(
                {"success": self._success, **stats,
                 "trace": str(self.trace_path)}, ensure_ascii=False, indent=2) + "\n")
        except Exception:  # noqa: BLE001 - result file is best effort
            pass
        try:
            self.env.close()
        except Exception:  # noqa: BLE001
            pass
        return stats


__all__ = ["Robot", "SafetyViolation", "Estop", "ConfirmationDenied"]
