*****************
Quickstart Manual
*****************

Working with Applications and Models
====================================

.. glossary::

    Application
        an abstraction which defines environment and software suite
        to utilize the Model with.

    Model
        a collection of settings typically represented as a config file
        for a software suite represented as Application.

Application Structure
---------------------

.. code-block:: json

    {
        'uid': 'f97c106dea0c4d26a3b9730c38ca89b2',
        'version': 0,
        'created': 1537378178.365059,
        'updated': 1537378178.365059,
        'owner': None,

        'name': None,
        'description': None,
        'attachment': None,
        'environment': {},
        'package': None
    }

.. glossary::

    uid
        object id
    version
        current object version
    created
        float value of unixtime ms then object was initially created
    updated
        float value of unixtime ms then object was updated last time
    owner
        id of a user who created the object
    name
        object user-defined name
    description
        object user-defined description
    attachment
        this is a system property, a link to a binary attachment, optionally uploaded for an object
    environment
        a dict of user-defined key-value pairs to be added as system environment variables on the runtime
    package
        a environment base to be used, currently it is a docker image id or reference, the only supported
        value is `buldozer_subordinate:latest`


Model Structure
---------------

.. code-block:: json

    {
        'uid': 'b6396e1627134c628166fa4ac7b88edc',
        'version': 0,
        'created': 1537378758.472685,
        'updated': 1537378758.472685,
        'owner': None,

        'name': None,
        'attachment': None
    }

.. glossary::

    uid
        object id
    version
        current object version
    created
        float value of unixtime ms then object was initially created
    updated
        float value of unixtime ms then object was updated last time
    owner
        id of a user who created the object
    name
        object user-defined name
    attachment
        this is a system property, a link to a binary attachment, optionally uploaded for an object


Creating an Application
-----------------------

to create an application use following request

.. code-block:: http

    >> POST /applications
    Content-Type: application/json
    X-User-Id: {user-id}
    {
        "name":"application name",
        "description":"application description",
        "package": "buldozer_subordinate:latest"
    }
    << HTTP 201 Created
    X-Version: 0
    {
        "uid": "created-app-id"
    }

.. note::
    application and models API uses versions passed explicitly in *X-Version* and *X-If-Version* headers
    to ensure you are working with object you intended to.

Listing existing Applications
-----------------------------

to list just created application use:

.. code-block:: http

    >> GET /applications
    X-User-Id: {user-id}
    << HTTP 200
    [
        {..app..},
        ...
    ]

Altering existing Application
-----------------------------

.. code-block:: http

    >> PUT /applications/{application-id}
    X-User-Id: {user-id}
    X-If-Version: {application-version}
    {
        "name":"application name",
        "description":"application description",
        "package": "buldozer_subordinate:latest"
        "environment": {
            "LOG_LEVEL": "DEBUG"
            "BDZ_PROGRAM": "cat"
        }
    }
    << HTTP 200 OK
    {
        ..app..
    }


Commit app version to archive
-----------------------------

In order to use application as an environment and provision it on the infrastructure it is required to
persist a copy of its current state to archive, which maintains a history of changes and provides reliable
access to all versions of application for internal services in order to keep ongoing changes isolated
from running instances and provide uninterrupted service and consistency.

To commit application version to archive, then you finished applying changes and ready to do so,
use following request:

.. code-block:: http

    >> POST /applications/{application-id}/commit
    X-User-Id: {user-id}
    X-If-Version: {application-version}
    << HTTP 200 OK
    {
        "version": {committed-version}
    }

Removing application
--------------------

application instance can be removed using following request

.. note::
    archive records will not be removed

.. code-block:: http

    >> DELETE /applications/{application-id}
    X-User-Id: {user-id}
    X-If-Version: {application-version}
    << HTTP 204 No Content
