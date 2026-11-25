# Docker Swarm for Enterprise Linux 9 and 10

The `docker_swarm` role installs Docker CE, enables and starts `docker.service`, and forms a Swarm from the inventory. It supports RHEL, Oracle Linux, AlmaLinux, Rocky Linux, and CentOS Stream 9 and 10 on `x86_64` and `aarch64`. By default, it uses Docker's stable RPM repository for each distribution with package signature verification enabled.

The role works with Ansible 2.10 or later and requires no external collections. Remote tasks use `ansible.builtin.raw` and an action plugin bundled with the role. Only the control node needs Python. Ansible 2.10 can run with Python 3.9 and Jinja2 3.0. [Ansible support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix)

## Install the role

From your Ansible project, clone this repository as `roles/docker_swarm`.

```bash
mkdir -p roles
git clone https://github.com/eldarsudden/docker_swarm.git roles/docker_swarm
```

Reference the role by name in your playbook.

```yaml
---
- name: Install Docker and configure Swarm
  hosts: docker_swarm
  gather_facts: false
  strategy: linear
  any_errors_fatal: true
  roles:
    - role: docker_swarm
```

## Prerequisites

1. Edit the `docker_swarm` group in `examples/inventory.yml`. Use hostnames or SSH aliases that the control node can connect to. Set the shared Swarm interface in the group variables and assign `docker_swarm_node_role: manager` or `docker_swarm_node_role: worker` to each host. Docker recommends three or five managers for high availability. [Swarm administration guide](https://docs.docker.com/engine/swarm/admin_guide/)
2. The role defaults to the first detected manager. To select a specific manager, set `docker_swarm_bootstrap_host` to its exact name under `hosts` in the inventory. For an existing cluster, select a reachable manager that already belongs to that Swarm.
3. Ensure the SSH user can run commands with `sudo` and the hosts can reach the enabled RPM repositories that provide the required packages.
4. Allow `2377/tcp` to managers, plus `7946/tcp`, `7946/udp`, and `4789/udp` between Swarm nodes. Encrypted overlay networks also need IP protocol 50 (ESP). Limit access to the cluster network. [Swarm network requirements](https://docs.docker.com/engine/swarm/swarm-tutorial/#open-protocols-and-ports-between-the-hosts)

Run the examples from the repository root in a checkout named `docker_swarm`. The bundled `ansible.cfg` adds the parent directory to the role search path. Use `-u` to select an SSH user and `-K` if `sudo` requires a password.

| Path | Purpose |
|---|---|
| [`examples/inventory.yml`](examples/inventory.yml) | Swarm inventory with managers, a worker, and shared settings. |
| [`examples/swarm.yml`](examples/swarm.yml) | Installs Docker CE, applies `daemon.json`, and joins nodes to the Swarm. |
| [`examples/backup.yml`](examples/backup.yml) | Backs up Swarm state on one manager. |
| [`examples/docker-inventory.yml`](examples/docker-inventory.yml) | Inventory for standalone Docker hosts. |
| [`examples/docker.yml`](examples/docker.yml) | Installs and configures Docker without creating a Swarm. |
| [`tasks/`](tasks/), [`defaults/`](defaults/), [`meta/`](meta/) | Role tasks, default variables, and metadata. |

The role also supports the `docker_swarm_managers` and `docker_swarm_workers` inventory groups. A host's explicit `docker_swarm_node_role` takes precedence. If the role of an existing node differs from the inventory, the play fails. Promote or demote the node using Swarm before reconciling its inventory entry.

### Swarm play requirements

- **Cluster scope.** The Swarm inventory groups must describe a single cluster. The inventory can include other groups, and the playbook can include other plays. Target only Swarm members in the play that runs this role.
- **Strategy.** Use `linear` so that all selected hosts finish each task before the next task starts. You can omit `strategy` when Ansible uses its default `linear` strategy.
- **Batch size.** Keep all selected hosts in one Ansible batch. You can omit `serial` or set it to `"100%"`. The role fails its inventory check if `serial` splits the selected hosts into multiple batches.
- **Fact gathering.** The examples use `gather_facts: false` because the role checks Docker directly. You can enable fact gathering if other tasks in the play need it.

Include every Swarm member when creating the cluster. For an existing cluster, `--limit` can select a subset that includes `docker_swarm_bootstrap_host`.

### Use an existing inventory group

Target your existing group in the play and assign `docker_swarm_node_role: manager` or `worker` to each Swarm host in the inventory.

```yaml
---
- name: Install Docker and configure Swarm
  hosts: minio
  gather_facts: false
  roles:
    - role: docker_swarm
```

For plays targeting the standard Swarm groups, the role uses those groups. For other plays, it discovers every host with `docker_swarm_node_role` in the inventory. This lets the role check that a first-time bootstrap includes every member, even when the command uses `--limit`. If one inventory contains several clusters with explicit node roles, set `docker_swarm_inventory_group` in the play to select the group for this cluster.

For backups with this inventory, target `minio` in the backup play and use `--limit` to select one manager.

## Usage

### Check the inventory

```bash
ansible-playbook -i examples/inventory.yml examples/swarm.yml --list-hosts
ansible-playbook -i examples/inventory.yml examples/swarm.yml --check
```

The first command lists the selected hosts. Check mode validates inventory groups, roles, and variables on the control node. Checking Docker state and network connectivity requires a normal run.

If bootstrap manager validation fails, compare `docker_swarm_bootstrap_host` with the detected managers printed in the error. If the list is empty, check that a cluster member has `docker_swarm_node_role: manager` or belongs to the legacy `docker_swarm_managers` group.

### Create a cluster

Run the play against every host in the Swarm inventory groups. Pass the initialization flag for this run.

```bash
ansible-playbook -i examples/inventory.yml examples/swarm.yml -e '{"docker_swarm_allow_init":true}'
```

On a manager, confirm that the nodes have the expected roles and show `Ready`.

```bash
sudo docker node ls
```

### Rerun the role or update daemon.json

Update `docker_swarm_daemon_config` in the inventory and run the playbook. The same command checks idempotence. Expect `changed=0` on a healthy cluster with unchanged settings.

```bash
ansible-playbook -i examples/inventory.yml examples/swarm.yml
```

### Add a worker to an existing cluster

Add an entry under `all.children.docker_swarm.hosts` in `examples/inventory.yml` and replace the example hostname. The worker inherits the Swarm interface from the group.

```yaml
swarm-w2:
  docker_swarm_node_role: worker
```

Include the configured bootstrap manager and the new host in the run. To add a manager, set `docker_swarm_node_role: manager` on the new host and use its name in `--limit`.

```bash
ansible-playbook -i examples/inventory.yml examples/swarm.yml --limit swarm-m1,swarm-w2
```

### Install Docker without creating a Swarm

Use the role's `install` entry point to install Docker CE, optionally apply `daemon.json`, and enable and start `docker.service`. This entry point requires neither `docker_swarm_node_role` nor `docker_swarm_advertise_addr`.

Replace `docker-1.example.com` with a hostname or SSH alias in [`examples/docker-inventory.yml`](examples/docker-inventory.yml). Set `docker_swarm_daemon_config: null` if you manage `daemon.json` separately. The [example playbook](examples/docker.yml) calls `tasks_from: install`.

```bash
ansible-playbook -i examples/docker-inventory.yml examples/docker.yml
```

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `docker_swarm_repo_enabled` | `true` | Enables the stable Docker CE RPM repository managed by this role. Set to `false` to install from the repositories already enabled on the host. |
| `docker_swarm_inventory_group` | Automatic | Optional inventory group that defines this cluster when one inventory contains multiple clusters. An explicit `docker_swarm` also includes the legacy manager and worker groups. |
| `docker_swarm_bootstrap_host` | First manager in the inventory | Inventory name of the manager used to initialize or access the cluster. |
| `docker_swarm_advertise_addr` | Required, inherited from the group or set per host | Swarm interface name or IP address. Examples with a port include `10.0.0.11:2377` and `[2001:db8::11]:2377`. |
| `docker_swarm_listen_addr` | `0.0.0.0:2377` | Swarm listen address and port for initialization or join. |
| `docker_swarm_data_path_addr` | Empty | IP address or interface for overlay traffic. Docker defaults to the advertised address. |
| `docker_swarm_daemon_config` | Debug disabled, `json-file` with `100m` and `3` files | YAML mapping written to `/etc/docker/daemon.json`. |
| `docker_swarm_node_role` | Inferred from legacy inventory groups | Desired host role, `manager` or `worker`. |
| `docker_swarm_node_labels` | `{}` | Labels to add or update on a Swarm node. |
| `docker_swarm_secrets` | `{}` | Swarm secret names mapped to their text values. |
| `docker_swarm_stacks` | `{}` | Stack names mapped to Compose file paths on the Ansible control node. |
| `docker_swarm_allow_init` | `false` | Explicitly allows cluster initialization for the current run. |
| `docker_swarm_default_addr_pools` | `[]` | List of CIDRs for overlay networks, used at `swarm init`. |
| `docker_swarm_default_addr_pool_mask_length` | Docker's default of `24` | Prefix length for each overlay subnet allocated from the configured pools. |
| `docker_swarm_backup_dir` | `/var/backups/docker-swarm` | Directory on the manager for Swarm state archives. |
| `docker_swarm_allow_single_manager_outage` | `false` | Allows a planned interruption when the cluster has one manager. |

## Set Swarm node labels

Set `docker_swarm_node_labels` on the host entry in the inventory.

```yaml
swarm-w1:
  docker_swarm_node_role: worker
  docker_swarm_node_labels:
    minio4: true
```

The role applies the labels through the bootstrap manager after the node joins and reports `Ready`. Boolean values become the strings `true` and `false`. You can use the label as a service placement constraint. [Docker Swarm node labels](https://docs.docker.com/reference/cli/docker/node/update/#label-add)

```yaml
deploy:
  placement:
    constraints:
      - node.labels.minio4==true
```

The role updates keys whose values differ and preserves other node labels.

## Create secrets and deploy stacks

Set these variables for the cluster in the inventory or play. Store real secret values in Ansible Vault and provide the matching password with `--ask-vault-pass` or `--vault-id`. Secret validation reports the name and reason on failure while keeping the value out of the task output.

```yaml
docker_swarm_secrets:
  app_password_v1: "{{ vault_app_password }}"
docker_swarm_stacks:
  storage: stacks/storage.yml
```

In the Compose file, reference the Swarm secret by name and declare it as external.

```yaml
version: "3.8"
services:
  example:
    image: busybox:1.36
    command: ["sleep", "3600"]
    secrets:
      - source: app_password_v1
        target: app_password
    deploy:
      placement:
        constraints:
          - node.labels.minio4==true
secrets:
  app_password_v1:
    external: true
```

The role applies node labels before creating missing secrets and deploying stacks on the bootstrap manager. It keeps existing secrets by name. To rotate a secret, create a new name and update the Compose file to reference it. [Docker Swarm secrets](https://docs.docker.com/engine/swarm/secrets/#example-rotate-a-secret)

The role reads Compose files on the control node using Ansible's standard file lookup, including the `files/` directory alongside the playbook. For example, `stacks/storage.yml` can resolve to `files/stacks/storage.yml`. If you provide only a filename such as `storage.yml`, the role also tries `stacks/storage.yml` as a fallback. Absolute paths are supported.

The role sends the file over standard input to `docker stack deploy` on the manager. The manager must be able to read files used by the Compose loader, such as `env_file`. Bind-mount sources must exist on the nodes that run the service. Each run submits every configured stack and reports the deployment as changed. [Docker stack deploy](https://docs.docker.com/reference/cli/docker/stack/deploy/)

## Use an existing RPM repository

If your hosts already use an internal Docker CE mirror, put the following setting in the inventory group variables.

```yaml
docker_swarm_repo_enabled: false
```

The role disables its existing `docker-swarm-ce-stable` entry. On a fresh host it leaves repository setup to your inventory or provisioning workflow. DNF still installs missing Docker CE, containerd, and CLI plugin packages from enabled repositories, so the mirror must provide those packages.

## Swarm advertise address

When all nodes use the same interface name for Swarm traffic, set `docker_swarm_advertise_addr` once under `all.children.docker_swarm.vars`. Replace `ens192` with the interface name on your hosts. Docker uses that interface's IP address on each node.

```yaml
all:
  children:
    docker_swarm:
      vars:
        docker_swarm_advertise_addr: ens192
      hosts:
        swarm-m1:
          docker_swarm_node_role: manager
        swarm-w1:
          docker_swarm_node_role: worker
          docker_swarm_advertise_addr: ens224
```

In this example, `swarm-m1` inherits `ens192` and `swarm-w1` overrides it with `ens224`. You can also override the group value with an explicit IP address. Use stable addresses on managers and ensure the advertised addresses are reachable from the other nodes. [Docker Swarm advertise address](https://docs.docker.com/engine/swarm/swarm-mode/#configure-the-advertise-address)

Docker can select the advertise address automatically when a node has a single IP address and `--advertise-addr` is omitted. This role requires an explicit value and passes it during `swarm init` and `swarm join`. [Docker Swarm join options](https://docs.docker.com/reference/cli/docker/swarm/join/#advertise-addr)

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

The role applies the following configuration by default. It recursively merges the effective inventory mapping into these defaults. Explicit values take precedence, nested mappings merge by key, and lists are replaced as a whole. For example, setting only `log-opts.max-file` keeps the default `log-opts.max-size`. Ansible's variable precedence determines which inventory mapping applies to each host. An empty mapping (`{}`) uses the defaults, and `null` leaves the existing file alone.

```yaml
all:
  vars:
    docker_swarm_daemon_config:
      debug: false
      log-driver: json-file
      log-opts:
        max-size: "100m"
        max-file: "3"
```

This example produces the following `/etc/docker/daemon.json`. Keep `log-opts` values as strings.

```json
{
  "debug": false,
  "log-driver": "json-file",
  "log-opts": {
    "max-file": "3",
    "max-size": "100m"
  }
}
```

Use bridge subnets that fit your network before enabling `bip` or `fixed-cidr`. Docker rejects options that duplicate flags passed at startup. The stock Docker CE systemd unit sets `-H fd://`, so leave `hosts` out of the mapping when using that unit. On an active Swarm node, changing `data-root` requires a separate data migration. [Docker daemon configuration](https://docs.docker.com/reference/cli/dockerd/#daemon-configuration-file)

The role applies changes one host at a time. Before restarting an active manager, it checks that a majority of managers will remain available. It waits for the restarted manager to report `Ready` and `Reachable` before moving to the next host. If the restart or readiness check fails, the role restores the previous file and attempts to recover the service. Check `journalctl -u docker.service` for service logs. Managers with autolock enabled require a separate maintenance procedure that includes unlocking. Run one maintenance playbook at a time for a given cluster.

If a manager restart is refused, check the actual Swarm manager list and autolock setting on that manager.

```bash
sudo docker node ls --filter role=manager
sudo docker info --format '{{.Swarm.Cluster.Spec.EncryptionConfig.AutoLockManagers}}'
```

In a four-manager Swarm, the other three managers must be reachable before the role can restart one. If cluster formation stopped after the first manager, set `docker_swarm_daemon_config: null` for the membership run. Apply the daemon configuration after the remaining managers join and become reachable. [Swarm manager quorum](https://docs.docker.com/engine/swarm/admin_guide/#maintain-the-quorum-of-managers)

## Rerun behavior

- The role installs missing packages and enables Docker at boot. Resolve any conflicts that DNF reports with previously installed packages before retrying. [Docker RPM installation](https://docs.docker.com/engine/install/rhel/)
- Initialization requires `docker_swarm_allow_init=true`, all Swarm inventory members in the play, and each member in the `inactive` state.
- For an existing cluster, the selected manager verifies the IDs and roles of active nodes. The play stops if a node belongs to a different Swarm or its role differs from the inventory.
- The role joins pending managers before workers and waits for selected nodes to report `Ready`. Ansible masks the output of token tasks, and SSH carries the join token over standard input.
- Swarm address settings apply during initialization or join. Configure firewall rules separately.

## Back up Swarm state

Select exactly one active manager. The archive is saved on that manager under `/var/backups/docker-swarm` by default.

```bash
ansible-playbook -i examples/inventory.yml examples/backup.yml --limit swarm-m1
```

To change the archive location, pass an absolute path on the manager.

```bash
ansible-playbook -i examples/inventory.yml examples/backup.yml --limit swarm-m1 \
  -e docker_swarm_backup_dir=/srv/backups/docker-swarm
```

The playbook checks quorum, stops Docker and its systemd socket, archives the `swarm` directory under the active `DockerRootDir`, and brings the manager back to `Ready` and `Reachable`. It prints the archive path after the run. The archive contains Swarm keys. Keep a protected copy off the manager and back up application volumes and external storage separately. [Swarm backup and recovery](https://docs.docker.com/engine/swarm/admin_guide/#back-up-the-swarm)
