# We're going to build our actual application, but not the actual production
# image that it gets deployed into.
FROM pypy:3-6.0.0-slim as build

# Define whether we're building a production or a development image. This will
# generally be used to control whether or not we install our development and
# test dependencies.
ARG DEVEL=no

# Install System level Linehaul build requirements, this is done before
# everything else because these are rarely ever going to change.
RUN set -x \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential libffi-dev libssl-dev \
        $(if [ "$DEVEL" = "yes" ]; then echo 'libjpeg-dev'; fi)

# We create an /opt directory with a virtual environment in it to store our
# application in.
RUN set -x \
    && pypy3 -m venv /opt/linehaul


# Now that we've created our virtual environment, we'll go ahead and update
# our $PATH to refer to it first.
ENV PATH="/opt/linehaul/bin:${PATH}"

# Next, we want to update pip, setuptools, and wheel inside of this virtual
# environment to ensure that we have the latest versions of them.
# TODO: We use --require-hashes in our requirements files, but not here, making
#       the ones in the requirements files kind of a moot point. We should
#       probably pin these too, and update them as we do anything else.
RUN pip --no-cache-dir --disable-pip-version-check install --upgrade pip setuptools wheel

# We copy this into the docker container prior to copying in the rest of our
# application so that we can skip installing requirements if the only thing
# that has changed is the Linehaul code itself.
COPY requirements /tmp/requirements

# Install the Python level Linehaul requirements, this is done after copying
# the requirements but prior to copying Linehaul itself into the container so
# that code changes don't require triggering an entire install of all of
# Linehaul's dependencies.
RUN set -x \
    && pip --no-cache-dir --disable-pip-version-check \
        install -r /tmp/requirements/main.txt \
                $(if [ "$DEVEL" = "yes" ]; then echo '-r /tmp/requirements/tests.txt'; fi) \
    && find /opt/linehaul -name '*.pyc' -delete





# Now we're going to build our actual application image, which will eventually
# pull in the static files that were built above.
FROM pypy:3-6.0.0-slim

# Setup some basic environment variables that are ~never going to change.
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /opt/linehaul/src/
ENV PATH="/opt/linehaul/bin:${PATH}"

WORKDIR /opt/linehaul/src/

# Copy the directory into the container, this is done last so that changes to
# Linehaul itself require the least amount of layers being invalidated from
# the cache. This is most important in development, but it also useful for
# deploying new code changes.
COPY --from=build /opt/linehaul/ /opt/linehaul/
COPY . /opt/linehaul/src/
