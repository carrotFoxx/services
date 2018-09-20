*****************
Quickstart Manual
*****************

Definitions
===========

.. glossary::

    Application
        an abstraction which defines environment and software suite
        to utilize the Model with.

    Model
        a collection of settings typically represented as a config file
        for a software suite represented as Application.

    Workspace
        an abstraction which defines runtime, by combining Application and Model in same environment,
        and provides options to stream data in and out for processing

Working with Applications
=========================

Application Structure
---------------------

.. code-block:: json

    {
        "uid": "874245b512304dfda1dc92ecd45b18ea",
        "owner": "1",
        "version": 1,
        "created": 1537454560.008261,
        "updated": 1537454560.052815,

        "name": "tavern test app",
        "package": "buldozer_subordinate:latest",
        "description": "cat used to pipe data",
        "attachment": null,

        "environment": {
            "LOG_LEVEL": "DEBUG",
            "BDZ_PROGRAM": "cat"
        }
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


Creating an Application
-----------------------

to create an application use following request

.. http:post:: /applications

    **example request**

    .. sourcecode:: http

        POST /applications
        Content-Type: application/json
        X-User-Id: 1

        {
            "name": "tavern test app",
            "package": "buldozer_subordinate:latest",
            "description": "cat used to pipe data",
            "environment": {
                "LOG_LEVEL": "DEBUG",
                "BDZ_PROGRAM": "cat"
            }
        }

    **example response**

    .. sourcecode:: http

        HTTP 201 Created
        X-Version: 0

        {
            "uid": "874245b512304dfda1dc92ecd45b18ea"
        }

    :<json *: Application object
    :>json uid: created application uid

.. note::
    application and models API uses versions passed explicitly in *X-Version* and *X-If-Version* headers
    to ensure you are working with object you intended to.

Listing existing Applications
-----------------------------

to list just created application use:

.. http:get:: /applications

    **example request**

    .. sourcecode:: http

        GET /applications
        X-User-Id: {user-id}

    **example response**

    .. sourcecode:: http

        HTTP 200 OK

        [
            {
                "uid": "874245b512304dfda1dc92ecd45b18ea",
                "owner": "1",
                "version": 1,
                "created": 1537454560.008261,
                "updated": 1537454560.052815,
                "name": "tavern test app",
                "package": "buldozer_subordinate:latest",
                "description": "cat used to pipe data",
                "attachment": null,
                "environment": {
                    "LOG_LEVEL": "DEBUG",
                    "BDZ_PROGRAM": "cat"
                }
            }
            ...
        ]

    :>jsonarr *: Application object

Altering existing Application
-----------------------------

.. http:put:: /applications/(uid)

    **example request**

    .. sourcecode:: http

        PUT /applications/874245b512304dfda1dc92ecd45b18ea
        X-User-Id: 1
        X-If-Version: 0

        {
            "name": "tavern test app",
            "package": "buldozer_subordinate:latest",
            "description": "cat used to pipe data",
            "environment": {
                "LOG_LEVEL": "DEBUG",
                "BDZ_PROGRAM": "cat"
            }
        }

    **example response**

    .. sourcecode:: http

        HTTP 200 OK

        {
            "uid": "874245b512304dfda1dc92ecd45b18ea",
            "owner": "1",
            "version": 1,
            "created": 1537454560.008261,
            "updated": 1537454560.052815,
            "name": "tavern test app",
            "package": "buldozer_subordinate:latest",
            "description": "cat used to pipe data",
            "attachment": null,
            "environment": {
                "LOG_LEVEL": "DEBUG",
                "BDZ_PROGRAM": "cat"
            }
        }

    :<json *: Application object
    :>json *: altered Application object

Commit app version to archive
-----------------------------

In order to use application as an environment and provision it on the infrastructure it is required to
persist a copy of its current state to archive, which maintains a history of changes and provides reliable
access to all versions of application for internal services in order to keep ongoing changes isolated
from running instances and provide uninterrupted service and consistency.

To commit application version to archive, then you finished applying changes and ready to do so,
use following request:

.. http:post:: /applications/(uid)/commit

    **example request**

    .. sourcecode:: http

        POST /applications/874245b512304dfda1dc92ecd45b18ea/commit
        X-User-Id: 1
        X-If-Version: 0

    **example response**

    .. sourcecode:: http

        HTTP 200 OK
        {
            "version": 1
        }

    :>json version: number of version in archive


Removing application
--------------------

application instance can be removed using following request

.. note::
    archive records will not be removed

.. http:delete:: /applications/(uid)

    **example request**

    .. sourcecode:: http

        DELETE /applications/874245b512304dfda1dc92ecd45b18ea
        X-User-Id: 1
        X-If-Version: 1

    :status 204: resource successfully removed

Working with Models
===================

Model Structure
---------------

.. code-block:: json

    {
        "uid": "8bc2037101b84dbda2ea9beae3573060",
        "owner": "1",
        "version": 1,
        "created": 1537454560.099979,
        "updated": 1537454560.154436,

        "name": "tavern test model",
        "attachment": "/opt/data/9a93136c-b2e6-439f-be1d-2be49187d8f3test_model_mgr.tavern.yaml"
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

.. http:any:: /models/(.*)

    Model API is structured in the same way as the Application API, so most queries are the same,
    except for the root path and object passed in POST and PUT, just switch it to Model structure.

    We will only cover the differences and additional APIs available.

Uploading Model Artifact
------------------------

.. http:post:: /models/(uid)/upload

    This is file upload endpoint, 2 different upload mechanics are supported.

    - http multipart/data (standard file upload as per RFC 7578)
    - body stream (streaming upload) - takes entire body of request as a file contents

    **example rfc7578 upload (simplified)**

    .. sourcecode:: http

        POST /models/{uid}/upload
        X-User-Id: {user-id}
        X-If-Version: {model-version}

        --multipart/binary--
        ....................
        ....binary data.....
        ....................

    **example stream upload**

    .. sourcecode:: http

        POST /models/{uid}/upload
        X-User-Id: {user-id}
        X-If-Version: {model-version}
        Content-Type: {file-content-type}

        ....................
        ....binary data.....
        ....................

    **example response**

    .. sourcecode:: http

        HTTP 200 OK

        {
            "Content-Type": "octetstream/binary",
            "_filename": "/opt/data/9a93136c-b2e6-439f-be1d-2be49187d8f3test_model_mgr.tavern.yaml",
            "_length": 674
        }

Utilizing Workspaces
====================

Workspaces are main configuration point to actually use the platform for things it is designed to.

Applications and Model are just definitions utilized by Workspace to provision runtime which processes data
streams and allows to route them in, out and from one workspace to another.

Workspace Structure
-------------------

.. code-block:: json

    {
        "uid": "3a2e81cd48984dd8af94ba5496f83bd8",
        "owner": "1",
        "created": 1537454560.208004,
        "updated": 1537454560.994276,

        "name": "tavern test",
        "app_id": "874245b512304dfda1dc92ecd45b18ea",
        "app_ver": 1,
        "model_id": "8bc2037101b84dbda2ea9beae3573060",
        "model_ver": 1,
        "instance_id": "2cf0efb712"
    }

.. glossary::

    uid
        object id
    created
        float value of unixtime ms then object was initially created
    updated
        float value of unixtime ms then object was updated last time
    owner
        id of a user who created the object
    name
        object user-defined name
    app_id
        application to bind in runtime
    app_ver
        application version to bind
    model_id
        model to bind in runtime
    model_ver
        model version to bind
    instance_id
        internal runtime id (may refer to Docker container, Kubernetes pod or OpenStack VM)


Creating Workspace
------------------

.. http:post:: /workspaces

    **example request**

    .. sourcecode:: http

        POST /workspaces
        X-User-Id: 1
        {
            "name": "tavern test",
            "app_id": "874245b512304dfda1dc92ecd45b18ea",
            "app_ver": 1,
            "model_id": "8bc2037101b84dbda2ea9beae3573060",
            "model_ver": 1
        }

    **example response**

    .. sourcecode:: http

        HTTP 201 Created
        {
            "uid": "3a2e81cd48984dd8af94ba5496f83bd8"
        }


    :<json *: Workspace object
    :>json uid: created workspace uid

Routing Kafka streams to and from Workspace
-------------------------------------------

.. http:put:: /workspaces/(uid)/route

    **example request**

    .. sourcecode:: http

        PUT /workspaces/3a2e81cd48984dd8af94ba5496f83bd8/route
        X-User-Id: 1

        {
            "incoming_stream": "events"
            "outgoing_stream": "results"
        }


    **example response**

    .. sourcecode:: http

        HTTP 204 No Content

    :<json string incoming_stream: kafka topic to consume data from
    :<json string outgoing_stream: kafka topic to write processed data to
    :status 204: route config stored in coordinator

.. http:get:: /workspaces/(uid)/route

    **example response**

    .. sourcecode:: http

        HTTP 200 OK

        {
            "desired_version": "1",
            "adopted_version": "1",
            "incoming_stream": "events",
            "outgoing_stream": "correlations"
        }

    :>json desired_version: incremental update number (incremented each time you update routing config)
    :>json adopted_version: incremental adopted number (equality of *desired* and *adopted* versions
                            indicates that config was successfully provisioned to runtime)
    :>json string incoming_stream: kafka topic to consume data from
    :>json string outgoing_stream: kafka topic to write processed data to
