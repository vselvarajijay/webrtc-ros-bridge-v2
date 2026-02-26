# Foxglove layouts for ConnectX

Use these with the **Gazebo simulation** (port 8766). For the webrtc/robot bridge use port 8765 instead.

## Open Foxglove and connect (one click)

With the [Foxglove desktop app](https://foxglove.dev/download) installed:

```bash
./scripts/open-foxglove-gazebo.sh
```

That opens the app and connects to `ws://localhost:8766`. Start the sim first: `docker compose --profile gazebo up gazebo`.

---

## First-time setup: full layout with robot URDF

Do this once to create the layout (3D panel with box car URDF, IMU, TF). Then export it so everyone can import and get the same setup.

### 1. Start the sim and open Foxglove

```bash
docker compose --profile gazebo up gazebo
# In another terminal:
./scripts/open-foxglove-gazebo.sh
```

### 2. Add the 3D panel (robot URDF)

- Click **Add panel** → **3D**.
- In the 3D panel settings (sidebar):
  - **Frame** → **Fixed frame:** set to **`world`** (so the grid and robot share a common origin).
  - **Scene** (or **URDF**) → **Add custom layer** → **URDF**.
  - In the URDF layer set the source in one of these ways:
    - **URL (recommended):** **Source** → **URL** → **`http://localhost:8767/box_car.urdf`** — sim serves this when running; avoids topic validation.
    - **Topic:** `/urdf/robot_description` or `/robot_description` (some setups report "invalid topic").
    - **URL (local):** `file:///ABSOLUTE_PATH_TO_REPO/ros2_ws/src/connectx_simulation/urdf/box_car.urdf` (Foxglove Desktop only).
  - Leave **Display mode** as **Visual** (or Auto). Turn on **Grid** (built-in layer) for a ground reference.
  - Optionally enable **Transforms** → **Labels** / **Axis scale** to see frame axes.
- You should see the box car (blue chassis, four wheels) and the grid in the 3D view.

**“Invalid topic: /robot_description”:** Use **Source** → **URL** → **`http://localhost:8767/box_car.urdf`** instead (sim must be running).

**If you only see arrows (TF axes) and no robot body:** Use **Source → Topic** with **`/urdf/robot_description`** (or **Source → URL** as above). Wait a few seconds after connecting so the transient_local message is received, or reconnect.

### 3. Add Raw Messages and TF (optional)

- **Add panel** → **Raw Messages** → set topic to `/imu/data` (e.g. check `linear_acceleration.z ≈ 9.8`).
- **Add panel** → **Transform (TF)** to inspect the tree: `chassis` → `wheel_fl`, `wheel_fr`, `wheel_rl`, `wheel_rr`.

### 4. Arrange layout (e.g. 3D on the right)

- Drag panels: put **3D** on the right (or full width), **Raw Messages** and **TF** on the left or bottom.
- Use **Split** (right-click or panel menu) to get e.g. left 1/3 (Raw Messages + TF stacked), right 2/3 (3D).

### 5. Export and commit the layout

- **Layouts** (sidebar or top menu) → current layout **⋮** → **Export…**
- Save as **`foxglove/connectx-gazebo-layout.json`** in this repo.
- Commit and push. Example: `git add foxglove/connectx-gazebo-layout.json && git commit -m "Add Foxglove layout for Gazebo sim (3D + URDF)"`.

After that, anyone can: connect via `./scripts/open-foxglove-gazebo.sh`, then **Layouts** → **Import from file…** → select `foxglove/connectx-gazebo-layout.json` to load the full setup with the robot URDF.

---

## Using an existing layout

If `connectx-gazebo-layout.json` exists in this folder:

1. Start the sim and open Foxglove: `./scripts/open-foxglove-gazebo.sh`
2. **Layouts** → **Import from file…** → choose `foxglove/connectx-gazebo-layout.json`
3. The 3D panel (fixed frame `world`, URDF from `/urdf/robot_description` or `/robot_description`), Raw Messages, and TF will load as configured.
