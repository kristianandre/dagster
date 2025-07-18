---
title: "Dagster Pipes details and customization"
description: "Learn about Dagster Pipes APIs and how to compose them to create a custom solution for your data platform."
sidebar_position: 90
---

[Dagster Pipes](/guides/build/external-pipelines) is a toolkit for integrating Dagster with an arbitrary external compute environment. While many users will be well-served by the simplified interface offered by Pipes client objects (e.g. <PyObject section="pipes" module="dagster" object="PipesSubprocessClient" />, <PyObject section="libraries" object="PipesDatabricksClient" module="dagster_databricks"/>), others will need a greater level of control over Pipes. This is particularly the case for users seeking to connect large existing codebases to Dagster.

This guide will cover the lower level Pipes APIs and how you can compose them to provide a custom solution for your data platform.

## Overview and terms

![Detailed overview of a Dagster Pipes session](/images/guides/build/external-pipelines/pipes-overview.png)

| Term | Definition |
|------|------------|
| **External environment** | An environment external to Dagster, for example: Databricks, Kubernetes, Docker. |
| **Orchestration process** | A process running Dagster code to materialize an asset. |
| **External process** | A process running in an external environment, from which log output and Dagster events can be reported back to the orchestration process. The orchestration process must launch the external process. |
| **Bootstrap payload** | A small bundle of key/value pairs that is written by the orchestration process to some globally accessible key-value store in the external process. Typically the bootstrap payload will be written in environment variables, but another mechanism may be used for external environments that do not support setting environment variables. |
| **Context payload** | A JSON object containing information derived from the execution context (<PyObject section="execution" module="dagster" object="AssetExecutionContext" />) in the orchestration process. This includes in-scope asset keys, partition keys, etc. The context payload is written by the orchestration process to some location accessible to the external process. The external process obtains the location of the context payload (e.g. an object URL on Amazon S3) from the bootstrap payload and reads the context payload. |
| **Messages** | JSON objects written by the external process for consumption by the orchestration process. Messages can report asset materializations and check results as well as trigger orchestration-side logging.|
| **Logs** | Log files generated by the external process, including but not limited to logged stdout/stderr streams. |
| **Params loader** | An entity in the external process that reads the bootstrap payload from some globally accessible key-value store. The default params loader reads the bootstrap payload from environment variables. |
| **Context injector** | An entity in the orchestration process that writes the context payload to an externally accessible location and yields a set of parameters encoding this location for inclusion in the bootstrap payload. |
| **Context loader** | An entity in the external process that loads the context payload from the location specified in the bootstrap payload. |
| **Message reader** | An entity in the orchestration process that reads messages (and optionally log files) from an externally accessible location and yields a set of parameters encoding this location in the bootstrap payload. |
| **Message writer** | An entity in the external process that writes messages to the location specified in the bootstrap payload. |

## Pipes session

A **Pipes session** is the time spanning:

1. The creation of communications channels between the orchestration and external process.
2. The launching and terminating of the external process.
3. The reading of all messages reported by the external process and the closing of communications channels.

There are separate APIs for interacting with a Pipes session in the orchestration and external processes. The orchestration process API is defined in `dagster`. The external process API is defined by a Pipes integration library that is loaded by user code in the external process. This library knows how to interpret the bootstrap payload and spin up a context loader and message writer.

At present the only official Dagster Pipes integration library is Python's [`dagster-pipes`](/api/libraries/dagster-pipes), available on [PyPI](https://pypi.org/project/dagster-pipes). The library has no dependencies and fits in a [single file](https://github.com/dagster-io/dagster/blob/master/python_modules/dagster-pipes/dagster_pipes/\__init\_\_.py), so it may also be trivially vendored.

### Session lifecycle (orchestration process)

Pipes sessions are represented in the orchestration process by the <PyObject section="pipes" module="dagster" object="PipesSession" /> class. A session is started with the <PyObject section="pipes" module="dagster" object="open_pipes_session" /> context manager, which yields a `PipesSession`. `open_pipes_session` should be called inside of an asset, where an <PyObject section="execution" module="dagster" object="AssetExecutionContext" /> is available:

<CodeExample path="docs_snippets/docs_snippets/guides/dagster/dagster_pipes/dagster_pipes_details_and_customization/session_lifecycle_orchestration.py" />

Above we see that <PyObject section="pipes" module="dagster" object="open_pipes_session" /> takes four parameters:

- `context`: An execution context (<PyObject section="execution" module="dagster" object="AssetExecutionContext" />) that will be used to derive the context payload.
- `extras`: A bundle of key-value pairs in the form of a JSON-serializable dictionary. This is slotted into the context payload. Users can pass arbitrary data here that they want to expose to the external process.
- `context_injector`: A context injector responsible for writing the serialized context payload to some location and expressing that location as bootstrap parameters for consumption by the external process. Above we used the built-in (and default) <PyObject section="pipes" module="dagster" object="PipesTempFileContextInjector" />, which writes the serialized context payload to an automatically created local temp file and exposes the path to that file as a bootstrap parameter.
- `message_reader`: A message reader responsible for reading streaming messages and log files written to some location, and expressing that location as bootstrap parameters for consumption by the external process. Above we used the built-in (and default) <PyObject section="pipes" module="dagster" object="PipesTempFileMessageReader" />, which tails an automatically created local temp file and exposes the path to that file as a bootstrap parameter.

Python context manager invocations have three parts:

1. An opening routine (`__enter__`, executed at the start of a `with` block).
2. A body (user code nested in a `with` block).
3. A closing routine (`__exit__`, executed at the end of a `with` block).

For <PyObject section="pipes" module="dagster" object="open_pipes_session" />, these three parts perform the following tasks:

- **Opening routine**: Writes the context payload and spins up the message reader (which usually involves starting a thread to continually read messages). These steps may involve the creation of resources, such as a temporary file (locally or on some remote system) for the context payload or a temporary directory to which messages will be written.
- **Body**: User code should handle launching, polling, and termination of the external process here. While the external process is executing, any intermediate results that have been received can be reported to Dagster with `yield from pipes_session.get_results()`.
- **Closing routine**: Ensures that all messages written by the external process have been read into the orchestration process and cleans up any resources used by the context injector and message reader.

### Session lifecycle (external process)

As noted above, currently the only existing Pipes integration library is Python's [`dagster-pipes`](/api/libraries/dagster-pipes). The below example therefore uses Python and `dagster-pipes`. In the future we will be releasing `dagster-pipes` equivalents for selected other languages. and the concepts illustrated here should map straightforwardly to these other integration libraries.

A Pipes session is represented in the external process by a <PyObject section="libraries" object="PipesContext" module="dagster_pipes" /> object. A session created by the launching orchestration process can be connected to with <PyObject section="libraries" object="open_dagster_pipes" module="dagster_pipes" /> from `dagster-pipes`:

<CodeExample path="docs_snippets/docs_snippets/guides/dagster/dagster_pipes/dagster_pipes_details_and_customization/session_lifecycle_external.py" />

:::tip

The metadata format shown above (`{"raw_value": value, "type": type}`) is part of Dagster Pipes' special syntax for specifying rich Dagster metadata. For a complete reference of all supported metadata types and their formats, see the [Dagster Pipes metadata reference](using-dagster-pipes/reference#passing-rich-metadata-to-dagster).

:::

Above we see that <PyObject section="libraries" object="open_dagster_pipes" module="dagster_pipes"/> takes three parameters:

- `params_loader`: A params loader responsible for loading the bootstrap payload injected into the external process at launch. The standard approach is to inject the bootstrap payload into predetermined environment variables that the <PyObject section="libraries" object="PipesEnvVarParamsLoader" module="dagster_pipes" /> knows how to read. However, a different bootstrap parameter loader can be substituted in environments where it is not possible to modify environment variables.
- `context_loader`: A context loader responsible for loading the context payload from a location specified in the bootstrap payload. Above we use <PyObject section="libraries" object="PipesDefaultContextLoader" module="dagster_pipes" />, which will look for a `path` key in the bootstrap params for a file path to target. The <PyObject section="pipes" module="dagster" object="PipesTempFileContextInjector" /> used earlier on the orchestration side writes this `path` key, but the `PipesDefaultContextLoader` does not otherwise depend on a specific context injector.
- `message_writer:` A message writer responsible for writing streaming messages to a location specified in the bootstrap payload. Above we use <PyObject section="libraries" object="PipesDefaultMessageWriter" module="dagster_pipes" />, which will look for a `path` key in the bootstrap params for a file path to target. The <PyObject section="pipes" module="dagster" object="PipesTempFileMessageReader" /> used earlier on the orchestration side writes this `path` key, but the `PipesDefaultMessageWriter` does not otherwise depend on a specific context injector.

As with the orchestration-side <PyObject section="pipes" module="dagster" object="open_pipes_session" />, <PyObject section="libraries" object="open_dagster_pipes" module="dagster_pipes" /> is a context manager. Its three parts perform the following functions:

- **Opening routine**: Reads the bootstrap payload from the environment and then the context payload. Spins up the message writer, which may involve starting a thread to periodically write buffered messages.
- **Body**: Business logic goes here, and can use the yielded <PyObject section="libraries" object="PipesContext" module="dagster_pipes" /> (in the `pipes` variable above) to read context information or write messages.
- **Closing routine**: Ensures that any messages submitted by business logic have been written before the process exits. This is necessary because some message writers buffer messages between writes.

## Customization

Users may implement custom params loaders, context loader/injector pairs, and message reader/writer pairs. Any of the above may be necessary if you'd like to use Dagster Pipes in an environment for which Dagster does not currently ship a compatible context loader/injector or message reader/writer.

### Custom params loader

Params loaders need to inherit from <PyObject section="libraries" object="PipesParamsLoader" module="dagster_pipes" />. Here is an example that loads parameters from an object called `METADATA` imported from a fictional package called `cloud_service`. It is assumed that "cloud service" represents some compute platform, that the `cloud_service` package is available in the environment, and that the API for launching processes in "cloud service" allows you to set arbitrary key-value pairs in a payload that is exposed as `cloud_service.METADATA`.

<CodeExample path="docs_snippets/docs_snippets/guides/dagster/dagster_pipes/dagster_pipes_details_and_customization/custom_bootstrap_loader.py" />

### Custom context injector/loader

Context injectors must inherit from <PyObject section="pipes" module="dagster" object="PipesContextInjector" displayText="dagster.PipesContextInjector" /> and context loaders from <PyObject section="libraries" object="PipesContextLoader" module="dagster_pipes" displayText="dagster_pipes.PipesContextLoader" />.

In general if you are implementing a custom variant of one, you will want to implement a matching variant of the other. Below is a simple example that uses a fictional `cloud_service` key/value store to write the context. First the context injector:

<CodeExample path="docs_snippets/docs_snippets/guides/dagster/dagster_pipes/dagster_pipes_details_and_customization/custom_context_injector.py" />

And the context loader:

<CodeExample path="docs_snippets/docs_snippets/guides/dagster/dagster_pipes/dagster_pipes_details_and_customization/custom_context_loader.py" />

### Custom message reader/writer

:::note

The message reader/writer is responsible for handling log files written by the
external process as well as messages. However, the APIs for customizing log
file handling are still in flux, so they are not covered in this guide. We
will update the guide with instructions for customizing log handling as soon
as these questions are resolved.

:::

Message readers must inherit from <PyObject section="pipes" module="dagster" object="PipesMessageReader" displayText="dagster.PipesMessageReader" /> and message writers from <PyObject section="libraries" module="dagster_pipes" object="PipesMessageWriter" displayText="dagster_pipes.PipesMessageWriter" />.

In general if you are implementing a custom variant of one, you will want to implement a matching variant of the other. Furtheremore, message writers internally create a <PyObject section="libraries" object="PipesMessageWriterChannel" module="dagster_pipes" /> subcomponent for which you will likely also need to implement a custom variant-- see below for details.

Below is a simple example that uses a fictional `cloud_service` key/value store as a storage layer for message chunks. This example is a little more sophisticated than the context injector/loader example because we are going to inherit from <PyObject section="pipes" module="dagster" object="PipesBlobStoreMessageReader" /> and <PyObject section="libraries" object="PipesBlobStoreMessageWriter" module="dagster_pipes" /> instead of the plain abstract base classes. The blob store reader/writer provide infrastructure for chunking messages. Messages are buffered on the writer and uploaded in chunks at a fixed interval (defaulting to 10 seconds). The reader similarly attempts to download message chunks at a fixed interval (defaulting to 10 seconds). This prevents the need to read/write a cloud service blob store for _every_ message (which could get expensive).

First, the message reader:

<CodeExample path="docs_snippets/docs_snippets/guides/dagster/dagster_pipes/dagster_pipes_details_and_customization/custom_message_reader.py" />

And the message writer:

<CodeExample path="docs_snippets/docs_snippets/guides/dagster/dagster_pipes/dagster_pipes_details_and_customization/custom_message_writer.py" />
