# Troubleshooting

## Instance is running but the Launchable is not ready

`brev ls --json` distinguishes VM state, build state, shell readiness, and
health. A running VM can still be executing the Launchable lifecycle script.
Wait for the official script to finish before starting another Docker Compose
operation.

## Viewer does not connect

1. Confirm the Launchable lifecycle script completed successfully.
2. Confirm the nginx, runtime, and web-viewer containers are running.
3. Confirm the secure link on port 80 is healthy.
4. Confirm the Isaac command logged `Simulation App Startup Complete`.
5. Keep only one `/viewer` browser tab open and refresh it after playback
   restarts.

Do not replace the secure link with an unauthenticated public endpoint.

## CLI cannot find the instance

Run `brev refresh`, then `brev ls`. Confirm the active Brev organization and
the exact `BREV_INSTANCE_NAME`.

## GPU is visible on the host but not in the container

Check `nvidia-smi` on the host, container status, and the container's
`NVIDIA_VISIBLE_DEVICES` configuration. Do not reinstall the NVIDIA driver
inside the official image.

## Out of disk

Inspect disk and Docker usage before deleting anything. Isaac images, shader
caches, logs, and checkpoints are large. Deleting the instance or persistent
disk requires separate approval.
