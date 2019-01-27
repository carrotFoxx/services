******************
Project Components
******************

.. note::
    `<kube-node>` notation means what service is available via
    mapped port at any/all nodes of the cluster

OpenStack
  Own cloud virtualization solution

Rancher
  Open-source software for delivering Kubernetes-as-a-Service.

  - <rancher-server>:8443

Kubernetes
  Container fleet management solution

  - <kube-node>:6443

mongodb
  Document-oriented database which stores all objects in the system
  as well as data produced by stream processors.

  - <kube-node>:30017

kafka
  Event broker, manages and handles all data-stream transfers
  between workspaces, and in and out of the system.

  - <kube-node>:30992
  - helm: git://git.crplab.ru/buldozer/kubernetes-infra

zookeeper
  Centralized service for maintaining configuration information,
  naming, providing distributed synchronization, and providing group
  services.

  We only use it for Kafka (as it is required).

consul
  Cloud-native distributed service-discovery and
  configuration management system

  - ui: consul.kube.crplab:80
  - api: <kube-node>:8500
  - helm: git://github.com/hashicorp/consul-helm

traefik
  Cloud-native L7 edge router and balancer

  - traefik.kuber.crplab:[80/443]

kafka-manager
  Management UI for Kafka cluster

  - kafka.kube.crplab:80
  - helm: git://git.crplab.ru/buldozer/kubernetes-infra

buldozer platform
  Handles management of app and model library and
  provisioning of workspaces inside the cluster

  - api.buldozer.kube.crplab
  - helm: git://git.crplab.ru/buldozer/kubernetes-infra
  - src: git://git.crplab.ru/buldozer/services
  - src: git://git.crplab.ru/gis/topic-manager

buldozer/gis UI
  UI for buldozer and gis services

  - web.buldozer.kube.crplab
  - helm: git://git.crplab.ru/buldozer/kubernetes-infra
  - src: git://git.crplab.ru/buldozer/webui


gis addon services
  API and Stream wrapper services to provide GIS-specific
  features

  - helm: git://git.crplab.ru/buldozer/kubernetes-infra
  - src: git://git.crplab.ru/gis/data-manager
  - src: git://git.crplab.ru/gis/backend-layer




