Buldozer General Architecture
=============================

.. uml:: diagrams/general.puml

Components:
-----------

.. describe:: App Manager

    service to manage Application types, configurations, instances and versions
    CRUD-like with REST based API

.. describe:: Model Manager

    service to manage Models, their types and versions
    CRUD-like with REST based API

.. describe:: Trainer Manager

    service to manage training process - RPC based, not directly accessible.
    takes App[ver] and DataSet to produce Model

.. describe:: Env Manager

    service to manage low-level environments for Applications to run in.
    An abstraction over container and virtual machine providers allowing
    to spin up an environment, provision App, Model and Supervisor to it
    and connect it to the platform for data and task receiving and processing

.. describe:: Supervisor

    a daemon deployed inside of container/vm to control desired application
    (acts as PID 1 in container), manages receiving incoming stream in slices
    and feeding it to application, then grabbing output and posting it back to stream

.. describe:: Stream Accessor

    service managing access to Kafka stream and turning it into a RPC/REST API
    to accumulate and return slices of stream of given length (in time or size)

.. describe:: Stream Saver

    service to save output stream data to DB (no RPC/REST access, just read and save from Kafka)

.. describe:: File Share

    distributed block or object store (Ceph, Minio, S3 or similar)

.. describe:: DB

    a PostgreSQL Database instance or cluster

.. describe:: API Gateway

    a solution like Kong or Tyk to manage access and routing of external calls to services
    of the platform
