#!/bin/bash
set -e

wait_for_line () {
	while read line ; do
		echo "$line" | grep -q "$1" && break
	done < "$2"
	# Read the fifo for ever otherwise process would block
	cat "$2" >/dev/null &
	WAIT_FOR_LINE_PID=$!
}

# Start MongoDB process for tests
MONGO_DATA=`mktemp -d /tmp/AODH-MONGODB-XXXXX`
MONGO_PORT=29000
mkfifo ${MONGO_DATA}/out
mongod --maxConns 32 --nojournal --noprealloc --smallfiles --quiet --noauth --port ${MONGO_PORT} --dbpath "${MONGO_DATA}" --bind_ip localhost --config /dev/null &>${MONGO_DATA}/out &
MONGO_PID=$!
# Wait for Mongo to start listening to connections
wait_for_line "waiting for connections on port ${MONGO_PORT}" ${MONGO_DATA}/out
# Read the fifo for ever otherwise mongod would block
cat ${MONGO_DATA}/out > /dev/null &
MONGO_DATA_PID=$!
export AODH_TEST_STORAGE_URL="mongodb://localhost:${MONGO_PORT}/AODH"

# Yield execution to venv command
OS_TEST_PATH=./aodh/tests/unit $*

# Kill all processes
kill ${WAIT_FOR_LINE_PID}
kill ${MONGO_PID}
kill ${MONGO_DATA_PID}
