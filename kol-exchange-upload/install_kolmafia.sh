#!/bin/bash

# Source: https://github.com/loathers/kolmafia-docker/blob/main/99-install-kolmafia

mkdir -p /tmp/kolmafia
cd /tmp/kolmafia

echo Downloading latest build of KoLmafia...
MAFIA_RELEASE=$(curl --fail --silent --globoff 'https://api.github.com/repos/kolmafia/kolmafia/releases/latest' | jq --raw-output '.assets[] | select(.browser_download_url | contains(".jar")).browser_download_url')
if [[ -z "$MAFIA_RELEASE" ]]; then
 	echo "ERROR: Could not determine latest mafia release from GitHub!"
 	exit 1
fi
wget -N --quiet "$MAFIA_RELEASE"

latest=$(ls -dt KoLmafia-*.jar | head -1)
oldest=$(ls -td KoLmafia-*.jar | awk 'NR>5')

if [ -n "$oldest" ]; then
	echo Removing old KoLmafia jar files...
	rm ${oldest}
fi

echo Linking kolmafia.jar from ${latest}...
if [ -f "kolmafia.jar" ]; then rm kolmafia.jar; fi
ln -s ${latest} kolmafia.jar
