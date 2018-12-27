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


Preparations
============

Docker Registry
---------------

We wont cover how to host Docker registry in this
manual, but consider following options:

- host manually, see `Docker Registry Docs`__ for info

  __ https://docs.docker.com/registry/

- registry is included in latest releases of GitLab CE/EE (see docs__)

  __ https://docs.gitlab.com/ee/administration/container_registry.html

- you can buy private registry hosting from:

  * Docker Hub
  * AWS
  * Azure

Or you can rely on CRPLab infrastructure and pull images from our own
registry (default)

To proceed you need to add your docker registry credentials to Kubernetes,
so images could be pulled and containers/services could be launched.

.. warning::
    Airgapped (physically isolated) installations are not covered
    by this manual.

To setup credentials to your registry of choice, first you need to
obtain them from the registry provider, in case of registry hosted by
CRPLab LLC you can receive credentials by mailing your manager.

Once you have acquired credentials from respective provider create
a secret in Kubernetes using following command:

.. code-block:: bash

    kubectl create secret docker-registry crplab \
        --docker-server=<DOCKER_REGISTRY_SERVER> \
        --docker-username=<DOCKER_USER> \
        --docker-password=<DOCKER_PASSWORD> \
        --docker-email=<DOCKER_EMAIL>

OR refer to this documentation__ for other options how to setup
access to private registry in Kubernetes

__ https://kubernetes.io/docs/concepts/containers/images/#using-a-private-registry

.. warning::
    Make sure to name secret "crplab", otherwise you will have to
    supply different secret name to all custom helm charts below

Building images
---------------

.. warning::
    This section is of interest only if you have been provided
    with access to source codes and wish to build
    artifacts (docker images) yourself. Otherwise - stick with
    images provided by developers of the system

Prerequisites:
  - docker installed
  - access to docker registry configured on your host
  - access to docker registry configured in Kubernetes

The only images you need to build are these of custom services
developed at CRPLab LLC, these are included in charts:

- buldozer-platform
- gis-addon/data-manager
- gis-addon/backend-layer

In general to build images you need to execute following commands:

.. code-block:: bash

    cd .../<subjected-source-code-repo>/

    docker build \
        -f <dockerfile> \
        -t <registry-addr/repo-name/image-name:image-tag> <context>

An example, how images are built in our CI:

.. code-block:: bash

    docker build \
        -f docker/Unsupervised.Dockerfile \
        -t registry.crplab.ru/buldozer/services:latest .

You'll find exact instructions on how to build specific images
in README's located with the source-codes of respective services.

Also, some services contain a `gitlab-ci.yaml` -
configuration for GitLab CI which builds images continuously,
you can use it as a reference to understand how images are built.


Cluster-Wide services install
=============================

MongoDB
-------

To provide persistent storage to MongoDB on SSD if you dont have "fast" class volumes provided by your platform
and Kubernetes via "dynamic-provisioning" you may need to setup SSD-backed NFS share.

When done, announce it to Kubernetes using following manifest and command (alter as necessary):

.. code-block:: bash

    cd ./kubernetes-setup
    kubectl create -f nfs.pv.yaml

After, you can provision MondoDB itself:

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


GIS Services Installation
=========================

.. code-block:: bash

    cd kubernetes/

    helm install ./gis-addon/backend-layer

    helm install ./gis-addon/data-manager

.. note::
    Make sure you reviewed values.yml and applied custom values
    to adjust the installation to your cluster.
