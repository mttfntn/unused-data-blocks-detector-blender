#!/usr/bin/env bash
# Download and unpack the supported Blender for CI, with retries, official
# mirrors and a checksum check. Usage: get-blender.sh <download-dir> <dest-dir>
# The verified tarball is kept in <download-dir> (cached by the workflow);
# the binary ends up at <dest-dir>/blender.
set -euo pipefail

VERSION="5.3.0"
SERIES="5.3"
FILE="blender-${VERSION}-linux-x64.tar.xz"
# From https://download.blender.org/release/Blender5.3/blender-5.3.0.sha256
SHA256="dacb8264197a3f7fda6001285a5a506fc97ee943881261c2c3bd63c882f22e05"
DL="$1"
DEST="$2"
mkdir -p "$DL"

MIRRORS=(
    "https://download.blender.org/release/Blender${SERIES}"
    "https://mirrors.ocf.berkeley.edu/blender/release/Blender${SERIES}"
    "https://ftp.nluug.nl/pub/graphics/blender/release/Blender${SERIES}"
    "https://mirror.clarkson.edu/blender/release/Blender${SERIES}"
)

ok=""
if [ -f "$DL/$FILE" ] && echo "${SHA256}  $DL/$FILE" | sha256sum -c - ; then
    echo "Using cached $FILE"
    ok=1
fi
for base in "${MIRRORS[@]}"; do
    [ -n "$ok" ] && break
    echo "Downloading ${base}/${FILE}"
    if curl -fL --retry 4 --retry-delay 5 --retry-all-errors --connect-timeout 20 \
            -A "Mozilla/5.0 (CI; unused-data-blocks-detector-blender)" \
            -o "$DL/$FILE" "${base}/${FILE}" \
       && echo "${SHA256}  $DL/$FILE" | sha256sum -c -; then
        ok=1
        break
    fi
    echo "Failed from ${base}, trying the next mirror"
done
[ -n "$ok" ] || { echo "Could not download Blender ${VERSION}"; exit 1; }

mkdir -p "$DEST"
tar -xJf "$DL/$FILE" -C "$DEST" --strip-components=1
"$DEST/blender" --version | head -1
