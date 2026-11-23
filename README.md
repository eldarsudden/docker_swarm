# Docker Swarm for Enterprise Linux 9 and 10

The `docker_swarm` role installs Docker CE, enables and starts `docker.service`, and forms a Swarm from the inventory. It supports RHEL, Oracle Linux, AlmaLinux, Rocky Linux, and CentOS Stream 9 and 10 on `x86_64` and `aarch64`. It uses Docker's stable RPM repository for each distribution and enables package signature verification.

The role works with Ansible 2.10 or later and requires no external collections. Remote tasks use `ansible.builtin.raw` and an action plugin bundled with the role. Only the control node needs Python. Ansible 2.10 can run with Python 3.9 and Jinja2 3.0. [Ansible support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix)

## Prerequisites

1. Edit the `docker_swarm` group in `inventory.yml`. Use hostnames or SSH aliases that the control node can connect to. Set `docker_swarm_advertise_addr` for each host and assign `docker_swarm_node_role: manager` or `docker_swarm_node_role: worker`. Docker recommends three or five managers for high availability. [Swarm administration guide](https://docs.docker.com/engine/swarm/admin_guide/)
2. Set `docker_swarm_bootstrap_host` in `swarm.yml` to a manager's inventory name. The examples use `swarm-m1`. For an existing cluster, choose a reachable manager that already belongs to that Swarm.
3. Ensure the SSH user can run commands with `sudo` and the hosts can reach the operating system and Docker repositories.
4. Allow `2377/tcp` to managers, plus `7946/tcp`, `7946/udp`, and `4789/udp` between Swarm nodes. Encrypted overlay networks also need IP protocol 50 (ESP). Limit access to the cluster network. [Swarm network requirements](https://docs.docker.com/engine/swarm/swarm-tutorial/#open-protocols-and-ports-between-the-hosts)

Run the examples from the repository root. Use `-u` to select an SSH user and `-K` if `sudo` requires a password.

| Path | Purpose |
|---|---|
| `inventory.yml` | Example inventory with managers, a worker, and shared settings. |
| `swarm.yml` | Installs Docker CE, applies `daemon.json`, and joins nodes to the Swarm. |
| `backup.yml` | Backs up Swarm state on one manager. |
| `roles/docker_swarm/` | Role used by both playbooks. |

The role also supports the `docker_swarm_managers` and `docker_swarm_workers` inventory groups. A host's explicit `docker_swarm_node_role` takes precedence. If the role of an existing node differs from the inventory, the play fails. Promote or demote the node using Swarm before reconciling its inventory entry.

Use one inventory per cluster. Run the role in a single play with `strategy: linear` and `gather_facts: false`, without batching hosts with `serial`.

## Usage

### Check the inventory

```bash
ansible-playbook -i inventory.yml swarm.yml --list-hosts
ansible-playbook -i inventory.yml swarm.yml --check
```

The first command lists the selected hosts. Check mode validates inventory groups, roles, and variables on the control node. Checking Docker state and network connectivity requires a normal run.

### Create a cluster

Run the play against every host in the inventory. Pass the initialization flag for this run.

```bash
ansible-playbook -i inventory.yml swarm.yml -e '{"docker_swarm_allow_init":true}'
```

On a manager, confirm that the nodes have the expected roles and show `Ready`.

```bash
sudo docker node ls
```

### Rerun the role or update daemon.json

Update `docker_swarm_daemon_config` in the inventory and run the playbook. The same command checks idempotence. Expect `changed=0` on a healthy cluster with unchanged settings.

```bash
ansible-playbook -i inventory.yml swarm.yml
```

### Add a worker to an existing cluster

Add an entry under `all.children.docker_swarm.hosts` in `inventory.yml`. Replace the example hostname and Swarm address with those of the new worker.

```yaml
swarm-w2:
  docker_swarm_advertise_addr: 192.0.2.22
  docker_swarm_node_role: worker
```

Include the configured bootstrap manager and the new host in the run. To add a manager, set `docker_swarm_node_role: manager` on the new host and use its name in `--limit`.

```bash
ansible-playbook -i inventory.yml swarm.yml --limit swarm-m1,swarm-w2
```

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `docker_swarm_bootstrap_host` | First manager in the inventory | Inventory name of the manager used to initialize or access the cluster. |
| `docker_swarm_advertise_addr` | Required for each host | Swarm IP address or interface name. Examples with a port include `10.0.0.11:2377` and `[2001:db8::11]:2377`. |
| `docker_swarm_listen_addr` | `0.0.0.0:2377` | Swarm listen address and port for initialization or join. |
| `docker_swarm_data_path_addr` | Empty | IP address or interface for overlay traffic. Docker defaults to the advertised address. |
| `docker_swarm_daemon_config` | Unset | YAML mapping written to `/etc/docker/daemon.json`. |
| `docker_swarm_node_role` | Inferred from legacy inventory groups | Desired host role, `manager` or `worker`. |
| `docker_swarm_allow_init` | `false` | Explicitly allows cluster initialization for the current run. |
| `docker_swarm_default_addr_pools` | `[]` | List of CIDRs for overlay networks, used at `swarm init`. |
| `docker_swarm_default_addr_pool_mask_length` | Docker's default of `24` | Prefix length for each overlay subnet allocated from the configured pools. |
| `docker_swarm_backup_dir` | `/var/backups/docker-swarm` | Directory on the manager for Swarm state archives. |
| `docker_swarm_allow_single_manager_outage` | `false` | Allows a planned interruption when the cluster has one manager. |

## Overlay address pools

Set the optional pool parameters in `all.vars` before creating the cluster.

```yaml
docker_swarm_default_addr_pools:
  - "10.240.0.0/16"
  - "10.241.0.0/16"
docker_swarm_default_addr_pool_mask_length: 24
```

Choose ranges that avoid overlaps with host networks, VPNs, local bridges, and other networks reachable from containers. Docker applies these settings when it initializes the Swarm. [Swarm address pools](https://docs.docker.com/engine/swarm/swarm-mode/#configuring-default-address-pools)

## Configure daemon.json

**Use any Linux `daemon.json` option supported by the installed Docker Engine.** Put the exact Docker option names and values in `docker_swarm_daemon_config`. The role serializes the entire YAML mapping into JSON, preserving value types and nested structures. It has no allowlist of option names. Docker checks the generated file with `dockerd --validate` before the role replaces the current file. [Docker reference for Linux `daemon.json` options](https://docs.docker.com/reference/cli/dockerd/#on-linux)

Set the mapping for all hosts, a group, or an individual host. Provide the full mapping at each level where you define it. With Ansible's default variable precedence, an override replaces the mapping. An unset variable leaves the file unmanaged. An empty mapping (`{}`) writes an empty JSON object.

```yaml
all:
  vars:
    docker_swarm_daemon_config:
      log-driver: json-file
      log-opts:
        max-size: "100m"
        max-file: "5"
      max-concurrent-downloads: 3
      max-concurrent-uploads: 5
      debug: false
```

This example produces the following `/etc/docker/daemon.json`. Keep `log-opts` values as strings.

```json
{
  "debug": false,
  "log-driver": "json-file",
  "log-opts": {
    "max-file": "5",
    "max-size": "100m"
  },
  "max-concurrent-downloads": 3,
  "max-concurrent-uploads": 5
}
```

Use bridge subnets that fit your network before enabling `bip` or `fixed-cidr`. Docker rejects options that duplicate flags passed at startup. The stock Docker CE systemd unit sets `-H fd://`, so leave `hosts` out of the mapping when using that unit. On an active Swarm node, changing `data-root` requires a separate data migration. [Docker daemon configuration](https://docs.docker.com/reference/cli/dockerd/#daemon-configuration-file)

The role applies changes one host at a time. Before restarting an active manager, it checks that a majority of managers will remain available. It waits for the restarted manager to report `Ready` and `Reachable` before moving to the next host. If the restart or readiness check fails, the role restores the previous file and attempts to recover the service. Check `journalctl -u docker.service` for service logs. Managers with autolock enabled require a separate maintenance procedure that includes unlocking. Run one maintenance playbook at a time for a given cluster.

## Rerun behavior

- The role installs missing packages and enables Docker at boot. Resolve any conflicts that DNF reports with previously installed packages before retrying. [Docker RPM installation](https://docs.docker.com/engine/install/rhel/)
- Initialization requires `docker_swarm_allow_init=true`, all inventory hosts in the play, and each host in the `inactive` state.
- For an existing cluster, the selected manager verifies the IDs and roles of active nodes. The play stops if a node belongs to a different Swarm or its role differs from the inventory.
- The role joins pending managers before workers and waits for selected nodes to report `Ready`. Ansible masks the output of token tasks, and SSH carries the join token over standard input.
- Swarm address settings apply during initialization or join. Configure firewall rules separately.

## Back up Swarm state

Select exactly one active manager. The archive is saved on that manager under `/var/backups/docker-swarm` by default.

```bash
ansible-playbook -i inventory.yml backup.yml --limit swarm-m1
```

To change the archive location, pass an absolute path on the manager.

```bash
ansible-playbook -i inventory.yml backup.yml --limit swarm-m1 \
  -e docker_swarm_backup_dir=/srv/backups/docker-swarm
```

The playbook checks quorum, stops Docker and its systemd socket, archives the `swarm` directory under the active `DockerRootDir`, and brings the manager back to `Ready` and `Reachable`. It prints the archive path after the run. The archive contains Swarm keys. Keep a protected copy off the manager and back up application volumes and external storage separately. [Swarm backup and recovery](https://docs.docker.com/engine/swarm/admin_guide/#back-up-the-swarm)
