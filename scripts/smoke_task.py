"""Smoke test for the Robot primitive API (stands in for generated code)."""
import sys

from agent.skills.api import Robot


def run() -> bool:
    R = Robot.from_env()
    try:
        R.log("smoke: settle then sort the small bolt")
        R.settle(30)
        R.pick("bolt_small_1")
        R.place("bolt_small_1", "parts_bin_blue_1")
        ok = R.check()
        R.home()
        return ok
    finally:
        R.close()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
