"""Send one DROID-shaped observation to an OpenPI server so it compiles before the rollout."""

import sys
import time

import numpy as np
import websockets.sync.client
from openpi_client import msgpack_numpy

port = int(sys.argv[1])
conn = websockets.sync.client.connect(
    f"ws://127.0.0.1:{port}", compression=None, max_size=None, ping_interval=None, close_timeout=10
)
print("server metadata:", msgpack_numpy.unpackb(conn.recv()))
img = np.zeros((224, 224, 3), dtype=np.uint8)
obs = {
    "observation/exterior_image_1_left": img,
    "observation/exterior_image_2_left": img,
    "observation/wrist_image_left": img,
    "observation/joint_position": np.zeros(7, dtype=np.float32),
    "observation/gripper_position": np.zeros(1, dtype=np.float32),
    "prompt": "pick up the banana",
}
packer = msgpack_numpy.Packer()
for i in range(2):
    t0 = time.time()
    conn.send(packer.pack(obs))
    reply = conn.recv()
    if isinstance(reply, str):
        sys.exit(f"server error:\n{reply}")
    actions = msgpack_numpy.unpackb(reply)["actions"]
    print(f"warmup inference {i}: {time.time() - t0:.1f} s, actions {np.shape(actions)}")
conn.close()
