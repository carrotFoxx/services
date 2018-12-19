**********************************
Infrastructure Installation Manual
**********************************

Prerequisites:
    - you have git and ssh installed
    - download the infrastructure repository from git
    - you have OpenStack cluster up and running

.. note::
    All commands described in this manual are expected to be run
    stating at the root of infrastructure repository.


Hardware/Platform Requirements
==============================

requirements for a hardware platform

Minimal (Single Node)
---------------------

- 8 logical CPUs
- 24Gb RAM
- 100Gb Storage

this will be sufficient to get system up and running to poke around.

Optimal (Single or Multi Node)
------------------------------

- 48 logical CPUs
- 64 Gb RAM
- 500 Gb Storage (HDD will do)
- 200-500 Gb Fast Storage (SDD or comparable)

Logical Layout Requirements
===========================

above mentioned resources should be presented to system in following
way (multi-node installation)

Table:

=========   =====   ======= =======
Node Type   LCPUs   RAM(Gb) Storage(Gb)
=========   =====   ======= =======
control     4       8       50 HDD
worker      8       16      100 HDD
storage     4       8       200 HDD, 200 SSD
=========   =====   ======= =======

Node Software Requirements
--------------------------

- OS: Ubuntu 16.04 LTS

no other basic requirements enforced.

Node setup
==========

Your machine setup
------------------

We use `ansible` to manage node software, recipes (playbooks)
contained in the repo.

To setup it on your machine - follow it's installation instructions,
which could be found at `docs.ansible.com`__

__ https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html

We use kubectl and helm to control deployment of services and supporting
software.

To setup kubectl - follow installation guide from `kubernetes.io`__

__ https://kubernetes.io/docs/tasks/tools/install-kubectl/

To setup helm - follow installation guide from `docs.helm.sh`__

__ https://docs.helm.sh/using_helm/#installing-helm

Setup nodes
-----------

Preparing your machine
~~~~~~~~~~~~~~~~~~~~~~

To begin, you need to enlist all nodes provisioned
in the ansible inventory file.

Refer to `inventory documentation at docs.ansible.com`__
for advanced usage.

__ https://docs.ansible.com/ansible/latest/user_guide/intro_inventory.html

Below is an example inventory configuration for setup of

- 1 control server
- 4 worker nodes
- 1 storage node

You should enlist nodes with aliases as in the example to make sure that all works as expected

.. code-block:: ini

    [all:vars]
    ansible_user=ubuntu
    ansible_python_interpreter=/usr/bin/python3

    [rancher-nodes]
    rancher-server ansible_host=10.0.0.17
    rancher-node-1 ansible_host=10.0.0.12
    rancher-node-2 ansible_host=10.0.0.13
    rancher-node-3 ansible_host=10.0.0.16
    rancher-node-4 ansible_host=10.0.0.9

    [rancher-control]
    rancher-server ansible_host=10.0.0.17

    [rancher-slaves]
    rancher-node-1 ansible_host=10.0.0.12
    rancher-node-2 ansible_host=10.0.0.13
    rancher-node-3 ansible_host=10.0.0.16
    rancher-node-4 ansible_host=10.0.0.9

    [storage-nodes]
    10.0.0.11

Make sure all nodes are reachable from your machine
use key-based ssh auth,
and are registered in your machines `known_hosts`.

You can make sure of it by simply logging in on each of them via:

.. code-block:: bash

    ssh ubuntu@<node-ip>

and accepting node's key as known.

Setting up nodes and deploying Rancher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prerequisites:
    - you have ansible, kubectl and helm installed
    - you have inventory.ini file with nodes you set up

To setup required software on the nodes, make sure all of them
have access to the internet and then execute following from
your machine:

.. code-block:: bash

    cd ./ansible
    ansible-playbook -i inventory.ini ./rancher-cluster-bootstrap.ans.yml

and wait for it to finish.

.. note::
    if something failed, run it again - it is idempotent

.. note::
    if you use non-default private key or non-direct network access to
    nodes, refer to `docs.ansible.com`_ to
    setup it and lookup options for `ansible-playbook` command required
    to make it work.

    Also take a look at this article_, explaining how to setup ansible
    to access nodes through jump host or bastion

.. _article: https://blog.scottlowe.org/2015/12/24/running-ansible-through-ssh-bastion-host/
.. _docs.ansible.com: https://docs.ansible.com

Also you need to setup shared storage node(s), to do so, apply next playbook:

.. code-block:: bash

    cd ./ansible
    ansible-playbook -i inventory.ini ./rancher-nfs.ans.yml

Outcome:
    - you have nodes software set up
    - rancher server software is running on the `control` node
    - you can access it via https://rancher-server:8443

Setup Rancher
~~~~~~~~~~~~~

Prerequisites:
    - you have nodes running and set up
    - rancher server software is running and accessible

Follow `this manual on rancher.com`__ to log in and setup Rancher.

In short:

#. Open a web browser and enter the IP address of rancher-server:
   `https://rancher-server:8443` (replace `rancher-server` with IP if needed)

#. When prompted, create a password for the default admin account.

#. Set the Rancher server URL, the URL can either be
   an IP address or a host name.
   However, each node added to your cluster must be able to connect to this URL.

.. note::
    If you use a hostname in the URL, this hostname must
    be resolvable by DNS on the nodes you want to add to you cluster.

__ https://rancher.com/docs/rancher/v2.x/en/quick-start-guide/deployment/quickstart-manual-setup/#3-log-in

Outcome:
    - you have Rancher UI fully operating

Setup Kubernetes cluster via Rancher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prerequisites:
    - you have running Racher and Racher UI ready
    - you have nodes set up and ready
    - you have infrastructure provider ready (openstack or similar, supported by Rancher)

Follow `this guide`__ to create a cluster and register your nodes.

__ https://rancher.com/docs/rancher/v2.x/en/quick-start-guide/deployment/quickstart-manual-setup/#4-create-the-cluster

While editing the cluster options, switch to "Edit as YAML" view,
and paste the contents of `rancher/rancher-cloud.conf.yaml` instead of
text contained where.

Make sure to alter settings, credentials and URL for OpenStack API under
`cloud_provider.openstackCloudProvider.**` to your installation details.

More info on options represented and how to setup them you can find in
`Rancher/RKE Documentation`__

__ https://rancher.com/docs/rke/v0.1.x/en/config-options/cloud-providers/openstack/


you can use following command to quickly launch node registration
process on all/selected nodes:

.. code-block:: bash

    ansible rancher-slaves \
            -i inventory.ini \
            -m shell -b \
            -a '<command you copied from Rancher UI>'

.. note::
    Make sure you register either 1 or 3 nodes with control-plane roles
    ("etcd" and "control-plane") and all or rest of them as "worker"


.. note::
    You can use other options provided by Rancher to setup Kubernetes Cluster,
    or even dont use Rancher at all, provision Kubernetes on bare-metal or
    using services like Istio, AWS EKS or Microsoft/Asure AKS.

    Rancher is not required for Buldozer to operate.

    However make sure Kubernetes has access to dynamically provisioned
    volumes (in case of openstack they are baked by openstack-cinder,
    other options could be: glusterfs, ceph, etc.. for full list of
    options head to `kubernetes documentation`__ and look for drivers
    supporting "dynamic provisioning")

__ https://kubernetes.io/docs/concepts/storage/volumes/#types-of-volumes

Once you have done with that - wait for cluster to become available
in Rancher UI (you will see its status either on main page or looking
at "Nodes" tab inside created cluster entry).

Outcome:
    - you have Kubernetes cluster ready and running

Segmenting your cluster
-----------------------

Prerequisites:
    - you have Kubernetes cluster ready and running
    - you have kubectl tool configured to access your cluster

In order to distribute load over the cluster and prevent conflicting
interest over resources certain components have additional scheduling
requirements which are based on labels of nodes and pods inside Kubernetes.

To get it working you should label some of the nodes according to
following table:

===================   ===========   ======
label                 value         amount
===================   ===========   ======
ru.crplab/dedicated   persistence   1
ru.crplab/dedicated   processing    1+
===================   ===========   ======

To list all nodes registered in Kubernetes:

.. code-block:: bash

    kubectl get nodes


To label node use following command:

.. code-block:: bash

    kubectl label nodes <node-name> <label-name>=<label-value>

Outcome:
    - you have nodes labeled in Kubernetes according to recommendations


Setup tooling
-------------

kubectl
~~~~~~~

Prerequisites:
    - Kubernetes cluster up and running
    - Rancher/UI up and running

Get configuration for kubectl from Rancher UI by heading to
cluster you have created in Rancher UI and selecting:

    > [You cluster] > [Kubeconfig File]

then follow instructions on the UI and put contents presented to `~/.kube/config`

.. note::
    If you are not using Rancher/UI, you have to obtain kube-config manually,
    and if you setup Kubernetes by other means, it is assumable that you now
    how to do this at that point

Helm and Tiller
~~~~~~~~~~~~~~~

Prerequisites:
    - Kubernetes cluster up and running
    - kubectl configured to access your cluster
    - helm installed on your machine

Run following command to setup Tiller in your cluster:

.. code-block:: bash

    helm init

Outcome:
    - Tiller installed in your cluster
    - helm is ready to install charts to your cluster


