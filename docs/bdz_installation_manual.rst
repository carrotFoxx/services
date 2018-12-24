****************************
Buldozer Installation Manual
****************************

Prerequisites:
    - git, ssh, kubectl and helm installed
    - downloaded the infrastructure repository from git
    - openstack cluster up and running
    - kubernetes cluster up and running

.. note::
    All commands described in this manual are expected to be run
    stating at the root of infrastructure repository.


Cluster-Wide services install
=============================


MongoDB
-------

.. code-block:: bash

    cd ./kubernetes-setup

    helm install stable/mongodb-replicaset \
        --version 3.6.3 \
        --name mongodb \
        --namespace gis \
        -f ./mongodb.config.helm.yaml

    kubectl create -f ../kubernetes/mongodb-external.service.yaml

Kafka+Zookeeper
---------------

.. code-block:: bash

    cd ./kubernetes

    kubectl create -f ./kafka.deployment.yaml

Kafka-Manager
~~~~~~~~~~~~~

Optionally you could install a control panel for Kafka

.. warning::
    Kafka-Manager has some control over Kafka and may expose
    security risks if installed on production system exposed
    to open networks

.. code-block:: bash

    cd ./kubernetes

    kubectl create -f ./kafka-manager.deployment.yaml

Consul
------


Download consul helm git repo prior execution

.. code-block:: bash

    cd ./kubernetes-setup

    git clone  https://github.com/hashicorp/consul-helm.git -b v0.2.0 --depth 1

Install helm chart

.. code-block:: bash

    cd ./kubernetes-setup

    helm install ./consul-helm \
        --name consul \
        --namespace consul \
        -f ./consul.config.helm.yaml

    kubectl create -f ./consul.rbac.yaml

Traefik Kubernetes ingress-controller
-------------------------------------

.. code-block:: bash

    cd ./kubernetes-setup

    helm install stable/traefik \
        --namespace kube-system \
        --name traefik \
        -f traefik_ingress.config.helm.yaml

Weave-Scope
-----------

Installation of this component is completely optional as it serves
only as informational panel.

.. code-block:: bash

    helm install stable/weave-scope \
        --name net-monitor \
        --namespace weave-scope

Kubernetes Dashboard
--------------------

Installation of this component is optional.

.. warning::
    Be careful if you choose to install this component, as it
    has admin privileges over cluster and can expose potential
    security risks.

.. code-block:: bash

    cd ./kubernetes-setup

    helm install stable/kubernetes-dashboard \
        --name k8sd \
        --namespace kube-system \
        -f ./k8s_dashboard.config.helm.yaml

    kubectl create -f ./k8s_dashboard.clusterrolebinding.yaml

Buldozer services installation
==============================

In fact it is pretty simple, all you have to do is install
buldozer-platform chart as you did with the rest of them

.. code-block:: bash

    cd kubernetes/

    helm install ./buldozer-platform

.. note::
    Make sure you reviewed values.yml and applied custom values
    to adjust the installation to your cluster (see below).

Buldozer Helm configuration
---------------------------

Things you should pre-configure yourself or note during the installation
of other components, such services, DNS names of
in-cluster components and IPs for infrastructure services located "below"
Kubernetes layer, which should be referenced in **buldozer helm values**.

.. note::
    Examine values.yaml for formats and other useful comments on how that
    should be configured

.. list-table:: Important Values

  * - value ref
    - description

  * - shared_fs.*
    - configures NFS volume pod-lifetime binding

  * - shared_fs.nfs_server
    - host IP or DNS name of NFS node

      should be accessible from all nodes in the cluster

  * - shared_fs.nfs_path
    - exported directory of NFS node

      should be r/w accessible for NFS client

  * - env-manager.environment.K8S_NFS_SHARE_SERVER
    - host IP or DNS name of NFS node

      should be accessible from all nodes

      in the cluster, must match `shared_fs.nfs_server`

  * - env-manager.environment.K8S_NFS_SHARE_PATH
    - exported directory of NFS node

      should be r/w accessible for NFS client

      must match `shared_fs.nfs_path`

  * - environment.*
    - these variables are provided to all pods of Buldozer

      and hold common DSNs for related services

  * - environment.MONGODB_DSN
    - DSN of mongodb there services store their data

      (usually it is deployed in-cluster as mentioned above)

  * - environment.CONSUL_DSN
    - DSN of consul there workspaces store their runtime
      configuration and post their healthchecks to.

      (usually it is deployed in-cluster as mentioned above)

  * - environment.KAFKA_DSN
    - DSN of kafka installation which processes all
      event-streams between workspaces

      (usually it is deployed in-cluster as mentioned above)

  * - environment.SENTRY_DSN:
    - DSN for Sentry error reporting, optional.

      (Sentry could be installed in-cluster or elsewhere).

      use "legacy" DSN format here (see Sentry UI to retrieve it)
