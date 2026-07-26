# Decisions

## 2026-07-25 — Use the official Isaac Launchable

Prefer the official preconfigured environment over a manual Isaac Sim and Isaac
Lab installation. This minimizes time to the first visible result and preserves
the official streaming stack.

## 2026-07-25 — Override the default GPU for Phase 0

The official Launchable recommends AWS `g6e.4xlarge` with one L40S at
approximately `$3.605088/hour`. For the simple CartPole MVP, use AWS
`g6.4xlarge` with one L4 and 64 GiB RAM at the last observed price of
`$1.59/hour` for compute.

This is a cost optimization outside the Launchable's recommended instance
configuration. If the L4 configuration fails due to a verified hardware or
memory constraint, stop it before considering the default L40S.

## 2026-07-25 — Use Boardman, Oregon for the MVP

Use AWS `us-west-2` (shown by Brev as Boardman, Oregon) to minimize interactive
streaming latency from the user's US West Coast location. The selected
configuration is stoppable and has flexible storage and ports.

The deployment UI reports approximately `$1.62-$1.63/hour` total: `$1.59/hour`
compute plus about `$0.04/hour` for the 256 GiB persistent disk. Stopping the
instance ends compute charges but the disk continues at about `$0.04/hour`.
