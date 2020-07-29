Linehaul
========

The Linehaul Statistics Daemon.

Linehaul is a daemon that implements the syslog protocol, listening for specially
formatted messages corresponding to download events of Python packages. For each
event it receives it processes them, and then loads them into a BigQuery database.


Usage
-----

General configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

    $ python -m linehaul -h
    Usage: linehaul [OPTIONS] COMMAND [ARGS]...

      The Linehaul Statistics Daemon.

      Linehaul is a daemon that implements the syslog protocol, listening for specially
      formatted messages corresponding to download events of Python packages. For each
      event it receives it processes them, and then loads them into a BigQuery database.

    Options:
      --log-level [spew|debug|info|warning|error|critical]
                                      The verbosity of the console logger.  [default:
                                      info]
      -h, --help                      Show this message and exit.

    Commands:
      migrate  Synchronizes the BigQuery table schema.
      server   Runs the Linehaul server.


Linehaul Server
~~~~~~~~~~~~~~~

.. code-block:: console

    $ python -m linehaul server -h
    Usage: linehaul server [OPTIONS] TABLE

      Starts a server in the foreground that listens for incoming syslog events,
      processes them, and then inserts them into the BigQuery table at TABLE.

      TABLE is a BigQuery table identifier of the form ProjectId.DataSetId.TableId.

    Options:
      --credentials-file FILENAME    A path to the credentials JSON for a GCP service
                                     account.
      --credentials-blob TEXT        A base64 encoded JSON blob of credentials for a GCP
                                     service account.
      --bind ADDR                    The IP address to bind to.  [default: 0.0.0.0]
      --port PORT                    The port to bind to.  [default: 512]
      --token TEXT                   A token used to authenticate a remote syslog stream.
      --max-line-size BYTES          The maximum length in bytes of a single incoming
                                     syslog event.  [default: 16384]
      --recv-size BYTES              How many bytes to read per recv.  [default: 8192]
      --cleanup-timeout SECONDS      How long to wait for a connection to close
                                     gracefully.  [default: 30]
      --queued-events INTEGER        How many events to queue for processing before
                                     applying backpressure.  [default: 10000]
      --batch-size INTEGER           The number of events to send in each BigQuery API
                                     call.  [default: 500]
      --batch-timeout SECONDS        How long to wait before sending a smaller than
                                     --batch-size batch of events to BigQuery.  [default:
                                     30]
      --retry-max-attempts INTEGER   The maximum number of times to retry sending a batch
                                     to BigQuery.  [default: 10]
      --retry-max-wait SECONDS       The maximum length of time to wait between retrying
                                     sending a batch to BigQuery.  [default: 60]
      --retry-multiplier SECONDS     The multiplier for exponential back off between
                                     retrying sending a batch to BigQuery.  [default: 0.5]
      --api-timeout SECONDS          How long to wait for a single API call to BigQuery to
                                     complete.  [default: 30]
      --api-max-connections INTEGER  Maximum number of concurrent connections to BigQuery.
                                     [default: 30]
      -h, --help                     Show this message and exit.


Schema Migrations
~~~~~~~~~~~~~~~~~

.. code-block:: console

    $ python -m linehaul migrate -h
    Usage: linehaul migrate [OPTIONS] TABLE

      Synchronizes the BigQuery table schema.

      TABLE is a BigQuery table identifier of the form ProjectId.DataSetId.TableId.

    Options:
      --credentials-file FILENAME  A path to the credentials JSON for a GCP service
                                   account.
      --credentials-blob TEXT      A base64 encoded JSON blob of credentials for a GCP
                                   service account.
      -h, --help                   Show this message and exit.


Discussion
----------

If you run into bugs, you can file them in our `issue tracker`_.

You can also join ``#pypa`` or ``#pypa-dev`` on Freenode to ask questions or
get involved.


.. _`issue tracker`: https://github.com/pypa/linehaul/issues


Code of Conduct
---------------

Everyone interacting in the Linehaul project's codebases, issue trackers, chat
rooms, and mailing lists is expected to follow the `PSF Code of Conduct`_.

.. _PSF Code of Conduct: https://github.com/pypa/.github/blob/main/CODE_OF_CONDUCT.md
