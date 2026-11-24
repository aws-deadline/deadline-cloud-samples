"""Print the versions and devices the training step will use, and fail if there is no GPU.

Newton runs its solver through NVIDIA Warp. Without a CUDA driver Warp falls back to the CPU
without reporting an error, which leaves training slow and sweep timings incomparable.
Failing here names the cause while the environment log is still in view.
"""

import sys


def main():
    import newton
    import torch
    import warp

    import isaaclab

    print("isaaclab  {}".format(isaaclab.__version__))
    print("warp      {}".format(warp.config.version))
    print("newton    {}".format(newton.__version__))
    print("torch     {} (cuda {})".format(torch.__version__, torch.version.cuda))

    warp.init()
    devices = [str(device) for device in warp.get_devices()]
    print("torch.cuda.is_available: {}".format(torch.cuda.is_available()))
    print("warp devices: {}".format(", ".join(devices)))

    cuda_devices = [device for device in devices if device.startswith("cuda")]
    if not cuda_devices:
        print(
            "ERROR: Warp found no CUDA device, so Newton would run on the CPU. Check that the "
            "step's amount.worker.gpu host requirement scheduled this onto an accelerated "
            "worker and that the NVIDIA driver is present.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
