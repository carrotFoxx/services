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
    make sure you reviewed values.yml and applied custom values
    to adjust the installation to your cluster

.. todo chart configuration highlight

