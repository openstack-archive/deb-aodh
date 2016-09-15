==============================
 Installing the API with uwsgi
==============================

Aodh comes with a few example files for configuring the API
service to run behind Apache with ``mod_wsgi``.

app.wsgi
========

The file ``aodh/api/app.wsgi`` sets up the V2 API WSGI
application. The file is installed with the rest of the Aodh
application code, and should not need to be modified.

Example of uwsgi configuration file
===================================


Create aodh-uwsgi.ini file::

    [uwsgi]
    http = 0.0.0.0:8041
    wsgi-file = <path_to_aodh>/aodh/api/app.wsgi
    plugins = python
    # This is running standalone
    master = true
    # Set die-on-term & exit-on-reload so that uwsgi shuts down
    exit-on-reload = true
    die-on-term = true
    # uwsgi recommends this to prevent thundering herd on accept.
    thunder-lock = true
    # Override the default size for headers from the 4k default. (mainly for keystone token)
    buffer-size = 65535
    enable-threads = true
    # Set the number of threads usually with the returns of command nproc
    threads = 8
    # Make sure the client doesn't try to re-use the connection.
    add-header = Connection: close
    # Set uid and gip to an appropriate user on your server. In many
    # installations ``aodh`` will be correct.
    uid = aodh
    gid = aodh

Then start the uwsgi server::

    uwsgi ./aodh-uwsgi.ini

Or start in background with::

    uwsgi -d ./aodh-uwsgi.ini

Limitation
==========

As Aodh is using Pecan and Pecan's DebugMiddleware doesn't support
multiple processes, there is no way to set debug mode in the multiprocessing
case. To allow multiple processes the DebugMiddleware may be turned off by
setting ``pecan_debug`` to ``False`` in the ``api`` section of
``aodh.conf``.

For other WSGI setup you can refer to the `pecan deployment`_ documentation.
.. _`pecan deployment`: http://pecan.readthedocs.org/en/latest/deployment.html#deployment
