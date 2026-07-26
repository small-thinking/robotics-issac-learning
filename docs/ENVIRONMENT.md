# Environment

## Local

Verified on 2026-07-25:

- macOS host
- Git `2.50.1`
- GitHub CLI `2.86.0`
- Homebrew `6.0.12`
- Brev CLI `v0.6.331`
- Codex CLI `0.146.0-alpha.3.1`

## Remote

Provisioning started on 2026-07-25:

- Brev instance: `isaac-launchable-f150a5` (`92xbacz46`)
- provider: AWS
- region: Boardman, Oregon (`us-west-2`)
- instance type: `g6.4xlarge`
- storage: 256 GiB
- GPU: 1x NVIDIA L4, 22.35 GiB visible VRAM in the Brev catalog
- CPU and RAM: 16 vCPU, 64 GiB
- instance can be stopped and restarted without losing the persistent disk
- secure tunnel requested by the Launchable: `isaac:80`
- firewall rule requested by the Launchable: `47998`

Record the following after the shell becomes ready:

- NVIDIA driver and CUDA;
- OS;
- Python;
- PyTorch;
- Isaac Sim;
- Isaac Lab;
- RL library and version.
