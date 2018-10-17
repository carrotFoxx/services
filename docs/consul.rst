*********************************
Consul KV structure specification
*********************************

This document describes KV namespaces and
structures used to express configurations
for Topic and DataManager services


Data-Manager configuration
==========================

Data-Manager configuration requires strong
consistency and cannot be changed on "per-key"
basis, therefore a pointer strategy should be
used to store configurations in KV stores

.. describe:: Pointer Strategy

    common approach to ensure consistent
    configuration changes and to prevent
    read of incomplete (mid-change, inconsistent)
    configuration


Actual Version Pointer
    this path should be checked for changes

    .. code-block::

        /gis/data-manager/version: {version-id}

    Example
        .. code-block::

            >> /gis/data-manager/version
            << 1


Path to config
    all config parts are stored in sub-keys
    under this path

    .. code-block::

        /gis/data-manager/{version}/

Routing config
    individual routes are stored under config path
    in separate keys and have following format

    a value in JSON:

    .. code-block::

        {
          "pattern":{
            "deviceVendor": "CISCO",
            "deviceProduct": "ASA"
          },
          "destination": "topic-123"
        }

    Route Path
        each individual rule is referenced
        by key meeting following pattern

        .. code-block::

            /gis/data-manager/{version}/{route-id}: {routing-config}

    Route ID (key name)
        is a hash of valuable unique combination
        of options defined by Route Config.

        In simple: it is a hash of all values which
        combination should not intersect between routes


Topic Manager configuration
===========================

Topic configurations are stored in Consul
and replicated to Kafka

Topic Manager configuration requires stateless
read for comparison and provisioning and
granular changes to maintain. Therefore a
define/adopt strategy is selected for KV stores

.. describe:: Define/Adopt Strategy

    this approach is based on fact what configuration
    is replicated in permanent matter from KV store
    elsewhere.

    writer changes the config and then "signals" to
    reader that fact via incrementing config version
    (`version indicator`)

    reader is watching `version indicator` changes
    and re-reads whole configuration on change

    after successfully replicating configuration
    reader sets `adoption indicator` to value matching
    version replicated, to indicate completion of
    process and do not repeat adoption process
    in case of restarts.

    writer or any other concerned party may watch
    for changes of `adoption indicator` to know
    if process was completed successfully


Root Path
    KV namespace

    .. code-block::

        /gis/topic-manager/

Strategy Indicators
    Adoption indicator
        holds version adopted, written
        by reader(adopter) only

        .. code-block::

            /gis/topic-manager/adopted_version: {int}

    Config Version Indicator
        holds version defined by writer(issuer)
        can be written by parties which are
        changing the config

        .. code-block::

            /gis/topic-manager/desired-version: {int}

Topic configs
    individual topic configs are stored under config path
    in separate keys and have following format (in JSON)

    .. code-block::

        {
            "name": "topic-123",
            "partitions": 5,
            "replicas": 3,
            "properties": {...}
        }

    Topic config path
        each individual topic config is located under
        key meeting following pattern.

        .. code-block::

            /gis/topic-manager/topics/{topic-name}: {topic config}

    Topic Name (Key)
        should match topic name in Kafka
