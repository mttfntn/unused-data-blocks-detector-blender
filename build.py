"""
Build the installable extension package.

    python build.py            -> dist/unused_data_blocks-<version>.zip

The zip uses Blender's extension layout: blender_manifest.toml and the Python
modules at the zip root, plus the LICENSE. The version comes from the manifest.
Validate it with:  blender --command extension validate dist/<zip>
"""

import os
import re
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "unused_data_blocks")
DIST = os.path.join(ROOT, "dist")


def manifest_version():
    with open(os.path.join(SRC, "blender_manifest.toml"), encoding="utf-8") as f:
        return re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.M).group(1)


def build():
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "unused_data_blocks-%s.zip" % manifest_version())
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(os.listdir(SRC)):
            path = os.path.join(SRC, name)
            if os.path.isfile(path) and name.endswith((".py", ".toml")):
                zf.write(path, name)
        zf.write(os.path.join(ROOT, "LICENSE"), "LICENSE")
    return out


if __name__ == "__main__":
    print("Wrote", build())
