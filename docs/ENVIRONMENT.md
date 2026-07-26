# Environment

## Local

Verified on 2026-07-25:

- macOS host
- Git `2.50.1`
- GitHub CLI `2.86.0`
- Homebrew `6.0.12`
- Brev CLI `v0.6.331`
- Codex CLI `0.146.0-alpha.3.1`

## Remote infrastructure

Verified on 2026-07-25:

- Brev instance: `isaac-launchable-f150a5` (`92xbacz46`)
- provider and region: AWS `us-west-2` (Boardman, Oregon in the Brev UI)
- instance type: `g6.4xlarge`
- storage: 256 GiB persistent disk
- GPU: 1x NVIDIA L4, 23,034 MiB in `nvidia-smi` (22.35 GiB catalog)
- CPU and RAM: 16 vCPU, 64 GiB
- host OS: Ubuntu 24.04.4 LTS
- host kernel: AWS Linux `6.17`
- NVIDIA driver: `595.71.05`
- `nvidia-smi` reported CUDA compatibility: `13.2`
- secure Launchable Viewer: authenticated Brev/NVIDIA route on `isaac:80`
- Launchable firewall port: `47998`

The instance can be stopped and restarted without losing the disk. The final
Phase 0 state is stopped; only persistent-storage billing remains.

## Isaac container

- image: `nvcr.io/nvidia/isaac-lab:3.0.0-beta2-post1`
- Isaac Sim: `6.0.1-rc.7+release.42383.32955d8d.gl`
- Isaac Lab extension: `isaaclab.python-3.0.0`
- Python: `3.12.13`
- PyTorch: `2.10.0+cu128`
- PyTorch CUDA build: `12.8`
- skrl: `2.1.0`
- Gymnasium: `1.2.1`

The host driver's reported CUDA compatibility and PyTorch's CUDA build version
are expected to differ; the successful GPU runs verified their compatibility.
All future checkpoint comparisons should pin this image or explicitly record
and validate the migration.
