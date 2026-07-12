#!/bin/sh
# pytest-clean-env — entrypoint shim used by docker-compose.test.yml
#
# The base docker-compose.yml injects DEBUG=true / ENVIRONMENT=
# development / LOG_LEVEL=DEBUG into the backend container for the
# dev stack. Compose merges ``environment:`` additively and cannot
# "unset" a variable from the test override. Several tests assert
# that ``Settings.debug_enabled`` is False and that
# ``configure_logging`` accepts the default INFO level, both of
# which require these three variables to be *absent* from the
# process environment, not merely set to empty strings.
#
# This script unsets the dev-mode vars and then exec's whatever
# command was passed via the compose ``command:`` field. Using
# ``exec`` (not just calling) keeps PID 1 stable so signal
# forwarding and container lifecycle work as expected.

unset DEBUG ENVIRONMENT LOG_LEVEL
exec "$@"
