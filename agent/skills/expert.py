"""Privileged scripted expert for the LIBERO bolt-sorting suite.

Pick a bolt (lying flat) by its hex head with a top-down parallel-jaw grasp,
carry it over the target parts bin and drop it in.  Uses the robot's
OperationalSpaceController: position + orientation deltas are both expressed in
the *world* frame (see robosuite/utils/control_utils.set_goal_position /
set_goal_orientation).

Only used to generate demonstration data -- it reads ground-truth object poses.
"""
import pathlib
import re
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
import robosuite.utils.transform_utils as T  # noqa: E402
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

TABLE_Z = 0.90

# geometry of the generated bolts (object frame: head centre at
# (-T/2 + H_h/2, 0, AF/2), bottom of the model at z=0)
BOLTS = {
    "bolt_small": dict(T=0.062, H_h=0.010, shank_l=0.052, AF=0.022, shank_d=0.013),
    "bolt_large": dict(T=0.103, H_h=0.018, shank_l=0.085, AF=0.038, shank_d=0.024),
}
# wooden cube used by the stacking (码垛) suite; must match
# vendor/wood-stack/gen_assets.py. The asset origin is the centre of the bottom
# face, so centre = pos + edge/2 and top face = pos + edge.
BLOCK = dict(edge=0.040)
POS_SCALE = 0.05      # controller output_max[:3]


class EpisodeDone(Exception):
    """raised when the LIBERO env terminates mid-plan (goal reached early)"""
ORI_SCALE = 0.50      # controller output_max[3:]


class Expert:
    def __init__(self, env):
        self.env = env
        self.u = env.env
        self.r = self.u.robots[0]
        self.c = self.r.controller
        self.table_z = TABLE_Z
        self.recorder = None      # optional callable(obs, action)
        # vision mode: when a VisionScene is attached, pose lookups come from the
        # RGB-D detections instead of the simulator. `refresh_vision` re-renders
        # one frame and updates the detections (used to verify grasps).
        self.vision = None
        self.refresh_vision = None
        self.last_obs = None          # callable -> most recent obs dict
        self.verbose_vision = False
        # EE pose right after reset: the one configuration the OSC always handles
        # cleanly. Used as a "re-center" waypoint before a stack placement.
        self.home_pos = self.ee()[0].copy()
        self.home_ori = self.ee()[1].copy()

    # ------------------------------------------------------------------ utils
    def body_pos(self, name):
        if self.vision is not None:
            return self.vision.body_pos(name)
        return self.u.sim.data.body_xpos[self.u.obj_body_id[name]].copy()

    def body_rot(self, name):
        if self.vision is not None:
            return self.vision.body_rot(name)
        return self.u.sim.data.body_xmat[self.u.obj_body_id[name]].reshape(3, 3).copy()

    def site_state(self, name):
        if self.vision is not None and name.endswith("_contain_region"):
            return self.vision.site_state(name)
        sid = self.u.sim.model.site_name2id(name)
        return (self.u.sim.data.site_xpos[sid].copy(),
                self.u.sim.data.site_xmat[sid].reshape(3, 3).copy(),
                self.u.sim.model.site_size[sid].copy())

    def ee(self):
        return self.c.ee_pos.copy(), self.c.ee_ori_mat.copy()

    def step(self, pos_err, ori_err, grip):
        if getattr(self.u, "done", False):
            raise EpisodeDone()
        a = np.zeros(7, dtype=np.float32)
        a[:3] = np.clip(np.asarray(pos_err) / POS_SCALE, -1, 1)
        a[3:6] = np.clip(np.asarray(ori_err) / ORI_SCALE, -1, 1)
        a[6] = grip
        out = self.env.step(a)
        obs = out[0] if isinstance(out, (tuple, list)) else out
        if self.recorder is not None:
            self.recorder(obs, a)
        return out

    def move_to(self, target_pos, target_ori, grip=-1.0, tol_p=0.010,
                tol_o=0.20, max_steps=100, speed=0.030, stall_patience=None,
                stall_tol=0.002):
        """P-controller on the (world-frame) pose error.

        `speed` caps the commanded position delta per control step (m) -- keep it
        small while carrying, otherwise the payload gets shaken out of the jaws.
        Returns the final (position, orientation) error.

        `stall_patience`: abort the move early when the position error has not
        improved by `stall_tol` (m) for that many steps. Without it a leg that
        saturates against a joint limit burns its whole max_steps budget (the
        v2 t6 transit used to spend 250 useless steps per failed leg).
        """
        err_p, err_o = 1e9, 1e9
        best, since_best = 1e9, 0
        for i in range(max_steps):
            p, R = self.ee()
            ep = np.asarray(target_pos) - p
            R_err = np.asarray(target_ori) @ R.T
            ax = T.quat2axisangle(T.mat2quat(R_err))
            err_p, err_o = np.linalg.norm(ep), np.linalg.norm(ax)
            self.step(np.clip(ep, -speed, speed),
                      np.clip(ax, -0.30, 0.30), grip)
            if err_p < tol_p and err_o < tol_o:
                break
            if stall_patience:
                if err_p < best - stall_tol:
                    best, since_best = err_p, 0
                else:
                    since_best += 1
                    if since_best >= stall_patience:
                        break
        return err_p, err_o

    def fingers_qpos(self):
        return np.array([self.u.sim.data.get_joint_qpos(j)
                         for j in self.r.gripper.joints])

    def set_gripper(self, cmd, steps=15):
        for _ in range(steps):
            self.step(np.zeros(3), np.zeros(3), cmd)

    # ------------------------------------------------------------- kinematics
    def grasp_orientation(self, axis_dir, R_cur=None):
        """EE orientation for a top-down grasp of a bolt lying along `axis_dir`.

        Facts established empirically on this gripper:
          * at home the EE z-axis points *down* (0,0,-1) and the hand extends
            along -z, so z_ee must stay (0,0,-1) for a straight-down approach;
          * the jaws close along x_ee (finger pads sit at x_ee = +-0.024).
        So x_ee has to be perpendicular to the bolt axis; both signs are
        equivalent grasps, pick whichever is closest to the current wrist pose.
        """
        z = np.array([0.0, 0.0, -1.0])
        u = np.array([axis_dir[0], axis_dir[1], 0.0])
        n = np.linalg.norm(u)
        if n < 1e-6:
            u = np.array([1.0, 0.0, 0.0])
            n = 1.0
        u = u / n
        v = np.cross(u, np.array([0.0, 0.0, 1.0]))
        v /= np.linalg.norm(v)
        cands = []
        for s in (1.0, -1.0):
            x = s * v
            y = np.cross(z, x)
            cands.append(np.stack([x, y, z], axis=1))
        if R_cur is None:
            return cands[0]
        def ang(R):
            return abs(T.quat2axisangle(T.mat2quat(R @ R_cur.T)).sum())
        return min(cands, key=ang)

    def bolt_axis(self, name):
        R = self.body_rot(name)
        u = R @ np.array([1.0, 0.0, 0.0])
        u[2] = 0.0
        return u / np.linalg.norm(u)

    @staticmethod
    def bolt_type(inst):
        """Instance name -> geometry key: bolt_small_1/_2 -> bolt_small."""
        return re.sub(r"_\d+$", "", inst)

    def head_center(self, name):
        """World position of the middle of the hex head."""
        sp = BOLTS[self.bolt_type(name)]
        R = self.body_rot(name)
        off = np.array([-sp["T"] / 2 + sp["H_h"] / 2, 0.0, sp["AF"] / 2])
        return self.body_pos(name) + R @ off

    def grasp_point(self, name):
        """Grasp the *shank* 25% along it from the head shoulder.

        Pinching the lying hex head with vertical jaw faces is unstable (the
        head is only H_h thick along the jaw's lateral axis and slips out);
        the smooth cylindrical shank gives a pure horizontal squeeze, and the
        head right behind the jaws acts as a flange against axial slippage.

        In vision mode the point comes from the RGB-D detection instead.
        """
        if self.vision is not None:
            return self.vision.grasp_point(name)
        sp = BOLTS[self.bolt_type(name)]
        R = self.body_rot(name)
        off = np.array([-sp["T"] / 2 + sp["H_h"] + 0.30 * sp["shank_l"],
                        0.0, sp["AF"] / 2])
        return self.body_pos(name) + R @ off

    # ---------------------------------------------------------------- episode
    def run(self, bolt, box, **kw):
        try:
            return self._run(bolt, box, **kw)
        except EpisodeDone:
            ok = bool(self.u._check_success())
            return ok, [("terminated", (0.0, 0.0))], True

    def _run(self, bolt, box, pre_h=0.10, lift_h=0.12, release_h=0.030,
             grasp_dz=0.0, verbose=False, grip_close_steps=35, settle_steps=30):
        """grasp() + transfer(); kept for demo collection and regression tests."""
        g_ok, glog = self.grasp(bolt, pre_h=pre_h, lift_h=lift_h, grasp_dz=grasp_dz,
                                verbose=verbose, grip_close_steps=grip_close_steps,
                                settle_steps=settle_steps)
        ok, tlog = self.transfer(box, release_h=release_h, verbose=verbose)
        return ok, glog + tlog, g_ok

    # ------------------------------------------------- split skill primitives
    def wrist_pixels(self) -> int:
        """Steel pixels between the jaws, from the wrist camera (0 if no frame)."""
        if not callable(getattr(self, "last_obs", None)):
            return 0
        obs = self.last_obs()
        if obs is None or "robot0_eye_in_hand_image" not in obs:
            return 0
        from agent.skills.perception import in_hand_pixels
        return in_hand_pixels(obs)

    def _spot_vacated(self, head) -> bool:
        """True when nothing steel is lying at table height where the part was."""
        if self.refresh_vision is None:
            return True
        scene = self.refresh_vision()
        before = np.asarray(head, dtype=float)
        for _name, rec in scene.bolts.items():
            c = np.asarray(rec["center"], dtype=float)
            if (np.linalg.norm(c[:2] - before[:2]) < 0.020
                    and c[2] < self.table_z + 0.05):
                return False
        return True

    def _vision_lift(self, bolt, head):
        """Visual grasp check, two independent signals.

        1. wrist camera: steel pixels between the fingers (empty jaws read
           176-260 px, a gripped part reads 1172-3316 px on this cell);
        2. scene camera: the space the part used to occupy is empty again --
           used as a cross-check when the wrist view is ambiguous.
        """
        from agent.skills.perception import in_hand_pixels, IN_HAND_PX
        obs = self.last_obs() if callable(getattr(self, "last_obs", None)) else None
        if obs is not None:
            wrist = in_hand_pixels(obs)
            if self.verbose_vision:
                print(f"   [vision] wrist steel px={wrist}")
            if wrist >= IN_HAND_PX:
                return 0.10
        before = np.asarray(head, dtype=float)
        scene = self.refresh_vision()
        for name, rec in scene.bolts.items():
            c = np.asarray(rec["center"], dtype=float)
            if (np.linalg.norm(c[:2] - before[:2]) < 0.020
                    and c[2] < self.table_z + 0.05):
                return 0.0
        return 0.10

    def _dropped_part(self, bolt, lift_h, tol=0.045) -> bool:
        """Privileged-mode carry check: is the part still up in the jaws?

        After the first transit leg the part should sit ~lift_h above the table.
        If it slipped it is back down (or gone), which used to be discovered only
        at the release, after the whole carry had been paid for.
        """
        try:
            z = float(self.body_pos(bolt)[2])
        except (KeyError, ValueError):
            return True
        return z < self.table_z + tol

    def _part_lost(self) -> bool:
        """Wrist-camera check: has the carried part slipped out of the jaws?"""
        if not callable(getattr(self, "last_obs", None)):
            return False
        obs = self.last_obs()
        if obs is None:
            return False
        from agent.skills.perception import part_in_hand
        return not part_in_hand(obs)

    def grasp(self, bolt, pre_h=0.10, lift_h=0.12, grasp_dz=0.0, verbose=False,
              grip_close_steps=35, settle_steps=30, attempts=2):
        """Settle, approach from above, close the jaws on the shank, lift.

        The jaw-encoder test alone is not reliable: the pads nearly meet when the
        jaws close on air (|qpos| ~ 0.005 still passes a 0.003 threshold), which
        is how a "successful" grasp ended up carrying nothing in the two-object
        task. So the grasp is verified by *observing the part move with the arm*
        and retried once from a fresh approach if it did not.

        Returns (grasp_ok, log). Leaves the bolt held; call transfer() next.
        """
        log = []
        for _ in range(settle_steps):
            self.step(np.zeros(3), np.zeros(3), -1.0)

        held = False
        for attempt in range(1, attempts + 1):
            head = self.grasp_point(bolt)
            axis = self.bolt_axis(bolt)
            R_grasp = self.grasp_orientation(axis, R_cur=self.ee()[1])
            z_before = self.body_pos(bolt)[2]

            self.set_gripper(-1.0, steps=12)

            tgt = head + np.array([0, 0, pre_h])
            err = self.move_to(tgt, R_grasp, grip=-1.0)
            if err[0] > 0.02:
                # Coming from the far side of the table (e.g. right after placing
                # the previous part) the wrist can saturate before reaching the
                # pre-grasp pose; climb and re-approach instead of closing on air.
                lift_z = max(tgt[2], self.table_z + 0.30)
                self.move_to(np.array([tgt[0], tgt[1], lift_z]), R_grasp, grip=-1.0,
                             max_steps=150)
                err = self.move_to(tgt, R_grasp, grip=-1.0)
            log.append((f"pre_grasp{attempt}", err)); _tr(verbose, "pre_grasp", self, bolt)

            tgt = head + np.array([0, 0, grasp_dz])
            err = self.move_to(tgt, R_grasp, grip=-1.0, tol_p=0.006, max_steps=80)
            log.append((f"descend{attempt}", err)); _tr(verbose, "descend", self, bolt)

            for _ in range(grip_close_steps):
                self.step(np.zeros(3), np.zeros(3), 1.0)
            jaw = float(np.abs(self.fingers_qpos()).mean())

            tgt = head + np.array([0, 0, lift_h])
            err = self.move_to(tgt, R_grasp, grip=1.0, max_steps=150, speed=0.015)
            if self.vision is not None and self.refresh_vision is not None:
                lifted = self._vision_lift(bolt, head)
            else:
                lifted = float(self.body_pos(bolt)[2] - z_before)
            log.append((f"lift{attempt}", (err[0], err[1])))
            if self.vision is not None:
                # the jaw encoder is unreliable here (pads close to ~1 mm on air
                # and on the head alike); the visual check is the signal
                held = lifted > 0.02
            else:
                held = lifted > 0.02 and jaw > 0.003
            if verbose:
                print(f"   [grasp] attempt {attempt}: jaw={jaw:.4f} lifted={lifted:.3f} "
                      f"held={held}")
            if held:
                break
            # not held: open, drop back to the settled pose, try once more
            self.set_gripper(-1.0, steps=10)
            self.move_to(head + np.array([0, 0, pre_h]), R_grasp, grip=-1.0,
                         max_steps=80)

        self._held = dict(bolt=bolt, head=head, R_grasp=R_grasp, lift_h=lift_h)
        return held, log

    # ------------------------------------------------------- stacking (码垛)
    def block_center(self, name):
        """World position of the block centre (asset origin = bottom centre)."""
        return self.body_pos(name) + np.array([0.0, 0.0, BLOCK["edge"] / 2.0])

    def block_top(self, name):
        """World position of the middle of the block's top face."""
        return self.body_pos(name) + np.array([0.0, 0.0, BLOCK["edge"]])

    def stack_orientation(self):
        """EE orientation for a cube: jaws close along the world y axis.

        Same gripper facts as grasp_orientation(): z_ee stays (0,0,-1) for a
        straight-down approach and the jaws close along x_ee.  Passing the world
        **x** axis as the "axis to straddle" therefore puts x_ee along y.

        This choice is not cosmetic.  A cube is symmetric, so both jaw directions
        grasp equally well, but the *arm* is not: with the jaws along x the IK
        branch chosen by the OSC cannot translate the EE in -x at stack height
        (measured t0 s1000/s1001: 115-135 mm short of the target, j4 pinned at its
        0.07 rad limit and the EE drifting +z instead of -x).  Rotating the same
        grasp 90 deg fixes it: dxy 12 mm, and the bent-arm route converges.
        """
        return self.grasp_orientation(np.array([1.0, 0.0, 0.0]), R_cur=self.ee()[1])

    def grasp_block(self, name, pre_h=0.10, lift_h=0.12, verbose=False,
                    attempts=2, settle_steps=25, grasp_h=0.012):
        """Top-down grasp of a cube near its bottom edge, verified by lift.

        `grasp_h` is measured from the block's bottom face, not from its centre.
        This matters: grasping at centre height puts the EE ~136 mm above the
        table, which is at the Panda's maximum extension for the far pick cells —
        q4 pins at its -0.07 rad limit and the Cartesian controller then cannot
        retract the arm at all (measured t5 s1001: unloaded retry stuck at the same
        126 mm error).  Gripping 12 mm above the table keeps the elbow bent and
        the whole workcell reachable.

        Same verification contract as grasp(): the jaw encoder cannot tell
        "closed on the part" from "closed on air", so the grasp is accepted only
        if the block actually rises with the arm ~lift_h.
        """
        log = []
        for _ in range(settle_steps):
            self.step(np.zeros(3), np.zeros(3), -1.0)

        held = False
        R_grasp = self.stack_orientation()
        for attempt in range(1, attempts + 1):
            centre = self.block_center(name)
            grip_pt = np.array([centre[0], centre[1], self.table_z + grasp_h])
            z_before = self.body_pos(name)[2]
            self.set_gripper(-1.0, steps=12)

            tgt = grip_pt + np.array([0.0, 0.0, pre_h])
            err = self.move_to(tgt, R_grasp, grip=-1.0, tol_p=0.015, max_steps=120)
            if err[0] > 0.02:
                # approaching from across the table the wrist can saturate; climb
                # and re-approach instead of closing the jaws on air
                lift_z = max(tgt[2], self.table_z + 0.30)
                self.move_to(np.array([tgt[0], tgt[1], lift_z]), R_grasp, grip=-1.0,
                             max_steps=150)
                err = self.move_to(tgt, R_grasp, grip=-1.0, tol_p=0.015)
            log.append((f"pre_grasp{attempt}", err))

            err = self.move_to(grip_pt, R_grasp, grip=-1.0, tol_p=0.006,
                               max_steps=90, speed=0.020)
            log.append((f"descend{attempt}", err))

            for _ in range(30):
                self.step(np.zeros(3), np.zeros(3), 1.0)
            jaw = float(np.abs(self.fingers_qpos()).mean())

            err = self.move_to(grip_pt + np.array([0.0, 0.0, lift_h]), R_grasp,
                               grip=1.0, max_steps=150, speed=0.015)
            lifted = float(self.body_pos(name)[2] - z_before)
            log.append((f"lift{attempt}", (err[0], err[1])))
            held = lifted > 0.02
            if verbose:
                print(f"   [stack] attempt {attempt}: jaw={jaw:.4f} "
                      f"lifted={lifted:.3f} held={held}")
            if held:
                break
            self.set_gripper(-1.0, steps=10)
            self.move_to(grip_pt + np.array([0.0, 0.0, pre_h]), R_grasp, grip=-1.0,
                         max_steps=80)

        self._held = dict(bolt=name, head=self.block_center(name),
                          R_grasp=R_grasp, lift_h=lift_h)
        return held, log

    def place_on_top(self, target, clear_h=0.022, verbose=False, over_tol=0.015,
                     carry_speed=0.015):
        """Carry the held block above `target` and release it onto its top face.

        Release height is `top + clear_h + edge/2` for the EE (= carried block
        centre).  clear_h is not 0 on purpose: the blocks are gripped near their
        bottom edge, so the finger pads sit at/below the part's bottom face and
        would hit the block underneath before the carried cube lands (measured
        t10 s1000: release at 10 mm left the cube leaning on the edge, dz 20 mm).
        Dropping the last ~22 mm onto a flat top face costs ~1 mm of xy accuracy.
        """
        held = getattr(self, "_held", None)
        if not held:
            raise RuntimeError("place_on_top() called with no block grasped")
        carried, R_grasp = held["bolt"], held["R_grasp"]
        edge = BLOCK["edge"]
        log = []

        top = self.block_top(target)
        ee_release = np.array([top[0], top[1], top[2] + clear_h + edge / 2.0])
        ee_above = np.array([top[0], top[1], top[2] + edge / 2.0 + 0.020])

        # 1) Transit height comes from the *stack*, not the table: for the third
        #    block of a tower the target top is already 0.98 m, and a fixed
        #    table+0.32 m transit (1.22 m) is unreachable there.
        ee = self.ee()[0]
        hi = max(float(ee[2]), top[2] + edge / 2.0 + 0.060)
        # Stacking on a block that already stands on something else needs the
        # bent-arm pose FIRST: a climb to the (high) transit height pins joint 4
        # on its lower limit, and from there the arm never recovers (measured
        # t0 s1000/s1001: every later route kept the same 115-135 mm error).
        high_target = top[2] > self.table_z + 0.06
        if not high_target:
            err = self.move_to(np.array([ee[0], ee[1], hi]), R_grasp, grip=1.0,
                               max_steps=150, speed=carry_speed, tol_p=0.05,
                               stall_patience=30)
            log.append(("climb", err))

        # 2) lateral traverse. A direct diagonal leg can pin joint 4 on its lower
        #    limit (q4 = -0.07 rad) while the arm is high and carrying: measured on
        #    t0 seed 1000, the EE froze 134 mm short of the stack and the placement
        #    was lost. Dropping to a bent-arm pose near the robot base first frees
        #    the elbow (same trick as the bin transfers); measured recovery 19.7 mm.
        routes = {
            # Re-centring: the pose the arm holds right after reset is the one the
            # OSC reproduces most reliably. Measured on the reach probe: from there
            # every stack target was reachable to <10 mm; from a pick pose far to
            # one side the same target stalls 110-140 mm short (j4 limit).
            "home_center": [(np.array([self.home_pos[0], self.home_pos[1],
                                       max(hi, self.table_z + 0.20)]), 200)],
            "direct": [],
            "bent_arm": [(np.array([0.05, 0.05, self.table_z + 0.10]), 160)],
            "bent_arm_mirror": [(np.array([-0.05, 0.05, self.table_z + 0.10]), 160)],
        }
        # Order matters: once joint 4 has been driven onto its limit the arm does
        # not recover (measured: every later route kept the same 114-135 mm error),
        # so the safe route always runs first.
        order = ["home_center", "bent_arm", "bent_arm_mirror", "direct"]
        err, chosen = (1e9, 0.0), None
        for name in order:
            for wp, msteps in routes[name]:
                self.move_to(wp, R_grasp, grip=1.0, max_steps=msteps, speed=0.020,
                             tol_p=0.050, stall_patience=30)
            err = self.move_to(np.array([top[0], top[1], hi]), R_grasp, grip=1.0,
                               max_steps=250, speed=carry_speed, tol_p=0.025,
                               stall_patience=40)
            dxy = float(np.linalg.norm(self.ee()[0][:2] - top[:2]))
            log.append((f"lateral:{name}", err))
            if chosen is None:
                chosen = name
            if dxy <= 0.030:
                chosen = name
                break
        if verbose:
            print(f"   [stack] lateral route={chosen} err={err[0]:.4f}")

        # 3) descend slowly onto the stack (a fast descent shakes the part loose)
        err = self.move_to(ee_above, R_grasp, grip=1.0, max_steps=120,
                           speed=0.012, tol_p=over_tol, stall_patience=30)
        err = self.move_to(ee_release, R_grasp, grip=1.0, max_steps=150,
                           speed=0.008, tol_p=0.006, stall_patience=40)
        log.append(("descend", err))

        # 4) release, retreat straight up, let the cube settle onto the stack
        self.set_gripper(-1.0, steps=25)
        self.move_to(ee_above, R_grasp, grip=-1.0, max_steps=120, speed=0.015,
                     stall_patience=30)
        for _ in range(40):
            self.env.step(np.array([0, 0, 0, 0, 0, 0, -1.0], dtype=np.float32))

        ok = self._stack_ok(carried, target)
        self._held = None
        return ok, log

    def _stack_ok(self, carried, target, dxy_tol=0.020, dz_tol=0.012):
        """Is `carried` now resting on `target`? (local check, not the goal)

        xy within 20 mm and one block height above the base; well inside the
        native `On` predicate's 30 mm / contact criterion, so a True here means
        the simulator's own goal check should agree.
        """
        try:
            c = self.body_pos(carried)
            t = self.body_pos(target)
        except (KeyError, ValueError):
            return bool(self.u._check_success())
        dxy = float(np.linalg.norm(np.asarray(c[:2]) - np.asarray(t[:2])))
        dz = float(c[2] - t[2])
        return bool(dxy <= dxy_tol and abs(dz - BLOCK["edge"]) <= dz_tol)

    def _local_placement_ok(self, bolt, box) -> bool:
        """Did *this* part land in *this* bin?

        The primitive used to return the episode-wide goal predicate, which is
        wrong for multi-part tasks: after the first of four placements the global
        predicate is still false, so every single `place` was reported as a
        failure (multi suite trace t10_s1001: 4/4 places "failed" while the parts
        were actually in the bins). Episode success still comes from the
        environment's goal predicate in `check()`.
        """
        try:
            pos, _R, size = self.site_state(f"{box}_contain_region")
            b = self.body_pos(bolt)
        except (KeyError, ValueError):
            return bool(self.u._check_success())
        # xy inside the cavity region (LIBERO's In() uses +-site_size; vision mode
        # reports the table height for lying parts, so z is not part of the test)
        dxy = np.abs(np.asarray(b[:2]) - np.asarray(pos[:2]))
        if dxy[0] > size[0] * 1.15 or dxy[1] > size[1] * 1.15:
            return False
        # in privileged mode also require the part to be at cavity height
        if self.vision is None:
            floor = pos[2] - size[2]
            rim = pos[2] + size[2]
            return bool(floor - 0.010 <= b[2] <= rim + 0.050)
        return True

    def transfer(self, box, release_h=0.030, verbose=False,
                 over_tol=0.020, into_tol=0.020, carry_speed=None):
        """Carry the held bolt over `box`, release it low, retreat, and report
        the episode goal check. Returns (ok, log).

        Tolerance note: the OSC controller keeps a steady-state error of
        ~12-17 mm on these transfer targets, so a 10 mm tolerance never
        converges and every move burns its full max_steps. 20 mm converges and
        is still far tighter than the bin opening (86-100 mm): measured effect
        628 -> 465 mean steps per episode with unchanged success.
        """
        held = getattr(self, "_held", None)
        if not held:
            raise RuntimeError("transfer() called with no bolt grasped")
        bolt, head = held["bolt"], held["head"]
        R_grasp, lift_h = held["R_grasp"], held["lift_h"]
        if carry_speed is None:
            # The small bolt's 13 mm shank gives the parallel pads very little to
            # hold on to: at 0.015 m/step the part slipped on the first climb in
            # ~1 of 4 vision episodes, and the multi-part suite's small-bolt tasks
            # were the weak spot (t1 3/10, t5 4/10, t9 4/10) while every large-bolt
            # task was 10/10. Carrying the small part at 0.010 m/step costs budget
            # but keeps it in the jaws.
            carry_speed = 0.010 if self.bolt_type(bolt) == "bolt_small" else 0.015
        log = []

        box_pos, box_rot, box_size = self.site_state(f"{box}_contain_region")
        cavity_floor = box_pos[2] - box_size[2]

        # Transit routing. A direct diagonal path to the bin can put the wrist on
        # the edge of the reachable set (task 0 seed 1001: the EE stalls around
        # x=0.08/y=0.23 and never reaches x=-0.17) where the OSC controller just
        # saturates against a joint limit. Route above the table first; if a leg
        # does not converge, retry through a waypoint above the robot base.
        def goto(target, max_steps, tol=over_tol):
            return self.move_to(np.asarray(target), R_grasp, grip=1.0,
                                max_steps=max_steps, speed=carry_speed, tol_p=tol)[0]

        ee_xy = self.ee()[0][:2].copy()
        bin_xy = np.asarray(box_pos[:2], dtype=float)
        hi_z = max(head[2] + lift_h, self.table_z + 0.30)
        mid_z = max(head[2] + lift_h, self.table_z + 0.22)
        carry_z = head[2] + lift_h

        def goto(target, max_steps, tol=over_tol, patience=30):
            return self.move_to(np.asarray(target), R_grasp, grip=1.0,
                                max_steps=max_steps, speed=carry_speed, tol_p=tol,
                                stall_patience=patience)[0]

        # Diagnosed on v2 t6 seeds 1001/1003: a single diagonal leg from the
        # pick pose straight over a far bin passes through a configuration where
        # joint 4 sits on its lower limit (q4 = -0.07) and the OSC controller
        # saturates -- the EE freezes ~28 cm short of the bin and the episode
        # times out. Inserting a half-way lateral waypoint (or retreating to a
        # bent-arm pose first) keeps the elbow off the limit: both recover to
        # <1 mm on the failing seeds. So the split route goes first.
        routes = {
            # High arc first: climb above the carry height so the lateral traverse
            # happens where the arm is least extended. Probed on the two seeds
            # that used to time out (v2 t6 s1001/s1003): every leg converges.
            "high_arc": [
                (np.array([ee_xy[0], ee_xy[1], hi_z + 0.14]), 120),
                (np.array([bin_xy[0] * 0.5, bin_xy[1] * 0.5, hi_z + 0.14]), 150),
                (np.array([bin_xy[0], bin_xy[1], hi_z + 0.14]), 180),
                (np.array([bin_xy[0], bin_xy[1], carry_z]), 200),
            ],
            # the old single-leg route, which is the fastest when it works
            "over_table": [
                (np.array([ee_xy[0], ee_xy[1], hi_z]), 120),
                (np.array([bin_xy[0], bin_xy[1], hi_z]), 200),
                (np.array([bin_xy[0], bin_xy[1], carry_z]), 200),
            ],
            "split": [
                (np.array([ee_xy[0], ee_xy[1], hi_z]), 120),
                (np.array([bin_xy[0] * 0.5, bin_xy[1] * 0.5, hi_z]), 150),
                (np.array([bin_xy[0], bin_xy[1], hi_z]), 180),
                (np.array([bin_xy[0], bin_xy[1], carry_z]), 200),
            ],
            "retreat": [
                (np.array([0.16, 0.00, self.table_z + 0.22]), 120),
                (np.array([0.05, 0.10, self.table_z + 0.30]), 120),
                (np.array([bin_xy[0], bin_xy[1], self.table_z + 0.30]), 180),
                (np.array([bin_xy[0], bin_xy[1], carry_z]), 200),
            ],
            "via_base": [
                (np.array([0.0, 0.0, mid_z]), 150),
                (np.array([bin_xy[0], bin_xy[1], mid_z]), 200),
                (np.array([bin_xy[0], bin_xy[1], carry_z]), 200),
            ],
        }
        # Only the *last* leg decides whether a route worked: the intermediate
        # waypoints are best-effort (the arm may top out a few cm short of a high
        # waypoint and that is harmless). Judging every leg is what made the old
        # code give up on routes that actually reach the bin.
        #
        # We also do NOT chase millimetres: the cavity is 172 mm across, so a
        # release up to ~60 mm off centre still drops the part inside. The old
        # code allowed that implicitly and scored 98%; requiring convergence first
        # made some reach-edge seeds burn the whole step budget instead.
        REACH_ENOUGH = 0.060
        best_dxy, chosen, err = 1e9, None, 1e9
        for name, legs in routes.items():
            for target, msteps in legs[:-1]:
                goto(target, msteps, tol=0.05)
            lost = (self._part_lost() if self.vision is not None
                    else self._dropped_part(bolt, lift_h))
            if lost:
                log.append((f"transit:{name}", "PART_LOST"))
                self._held = None
                return False, log
            target, msteps = legs[-1]
            err = goto(target, msteps, tol=over_tol)
            dxy = float(np.linalg.norm(self.ee()[0][:2] - bin_xy))
            log.append((f"transit:{name}", err))
            if dxy < best_dxy:
                best_dxy, chosen = dxy, name
            if dxy <= REACH_ENOUGH:
                break
        if verbose:
            print(f"   [transit] route={chosen or 'fallback'} err={err:.4f}")

        tgt_p = np.array([box_pos[0], box_pos[1], carry_z])
        err = self.move_to(tgt_p, R_grasp, grip=1.0, max_steps=200,
                           speed=carry_speed, tol_p=over_tol, stall_patience=40)
        log.append(("over_bin", err)); _tr(verbose, "over_bin", self, bolt)

        # Release just above the cavity floor. The old rule clamped to
        # table_z+0.05, which for the 45 mm blue bin is *below its rim* and for
        # the 65 mm red bin 25 mm inside it: the pads ended up straddling a wall
        # and the part bounced out. Keep the release inside the cavity but low.
        tgt_p = np.array([box_pos[0], box_pos[1],
                          max(cavity_floor + min(release_h, 0.012),
                              self.table_z + 0.015)])
        err = self.move_to(tgt_p, R_grasp, grip=1.0, tol_p=into_tol, max_steps=200,
                           speed=carry_speed, stall_patience=40)
        log.append(("into_bin", err)); _tr(verbose, "into_bin", self, bolt)
        self.set_gripper(-1.0, steps=20)

        tgt_p = np.array([box_pos[0], box_pos[1], carry_z])
        self.move_to(tgt_p, R_grasp, grip=-1.0, max_steps=60, stall_patience=25)

        for _ in range(25):
            self.env.step(np.array([0, 0, 0, 0, 0, 0, -1.0], dtype=np.float32))

        ok = self._local_placement_ok(bolt, box)
        self._held = None
        return ok, log


def _tr(verbose, tag, ex, bolt):
    if not verbose:
        return
    try:
        bp = np.round(ex.body_pos(bolt), 4)
    except KeyError:
        bp = "(not visible)"   # vision mode: the part is in the jaws
    print("   [trace] %-9s ee %s bolt %s" % (tag, np.round(ex.ee()[0], 4), bp))


def build_env(task_bddl, cameras=(64, 64), seed=0):
    bddl = pathlib.Path(get_libero_path("bddl_files")) / task_bddl
    h, w = cameras
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=h, camera_widths=w)
    env.seed(seed)
    env.reset()
    return env


if __name__ == "__main__":
    import argparse
    from libero.libero.benchmark import get_benchmark_dict

    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="libero_bolt")
    ap.add_argument("--task_idx", type=int, default=-1, help="-1 = all tasks")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    suite = get_benchmark_dict()[args.suite]()
    bddl_dir = pathlib.Path("libero_bolt")
    idxs = (range(suite.get_num_tasks()) if args.task_idx < 0
            else [args.task_idx])
    tot_ok = tot = 0
    for i in idxs:
        task = suite.get_task(i)
        bddl = f"bddl_files/libero_bolt/{task.bddl_file}" if False else \
            pathlib.Path(get_libero_path("bddl_files")) / "libero_bolt" / task.bddl_file
        env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64,
                                 camera_widths=64)
        ok_n = 0
        for a in range(args.attempts):
            env.seed(1000 * i + a)
            env.reset()
            expert = Expert(env)
            lang = task.language
            if "small" in lang and "large" in lang:
                bolts = ["bolt_small_1", "bolt_large_1"]
            elif "small" in lang:
                bolts = ["bolt_small_1"]
            elif "large" in lang:
                bolts = ["bolt_large_1"]
            else:
                bolts = ["bolt_small_1", "bolt_large_1"]
            boxes = []
            for b in bolts:
                boxes.append("parts_bin_blue_1" if "small" in b
                             else "parts_bin_red_1")
            res = []
            for b, bx in zip(bolts, boxes):
                ok, log, grasped = expert.run(b, bx, verbose=args.verbose)
                res.append((b, ok, grasped))
                if args.verbose:
                    print("   ", b, "->", bx, "grasped=", grasped, "success=", ok,
                          "phases=", [(n, round(e[0], 4), round(e[1], 3))
                                      for n, e in log])
            ok_n += all(r[1] for r in res)
            print(f"[task {i:2d}] {task.language[:46]:46s} attempt {a}: "
                  + " ".join(f"{b}={'OK' if o else 'x'}(grasp={g})"
                             for b, o, g in res))
        tot_ok += ok_n; tot += args.attempts
        print(f"[task {i:2d}] {ok_n}/{args.attempts}")
        env.close()
    print(f"\nEXPERT SUCCESS: {tot_ok}/{tot} = {100.0 * tot_ok / max(tot, 1):.1f}%")
