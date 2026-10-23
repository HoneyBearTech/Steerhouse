"""Checks the Heimdall app package the way linuxserver/Heimdall-Apps' own tests do (apps.tests.js),
so a submission doesn't fail there:

    python3 integrations/heimdall/check_package.py

The PHP itself is checked by CI with `php -l` (PHP 8.2) and PHPCS (PSR-12), as upstream does.
"""

import hashlib
import json
import re
import struct
import sys
import unicodedata
from pathlib import Path
from xml.etree import ElementTree

APP = Path(__file__).resolve().parent / "Steerhouse"
FIELD_ORDER = [
    "appid",
    "name",
    "website",
    "license",
    "description",
    "enhanced",
    "tile_background",
    "icon",
]


def slug(name: str) -> str:
    """Laravel's Str::slug(name, ''), as upstream's scripts/lib/slug.js reproduces it."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"-+", "", text).replace("@", "at").lower()
    return re.sub(r"\s+", "", re.sub(r"[^a-z0-9\s]+", "", text))


def svg_problem(icon: Path) -> str | None:
    """Why the SVG isn't a plain drawing that reads the same everywhere (Heimdall sanitises SVGs,
    and upstream's svgo pass removes the root's size), or None."""
    try:
        root = ElementTree.parse(icon).getroot()  # noqa: S314 - our own file, not input
    except ElementTree.ParseError as exc:
        return f"not well-formed XML ({exc})"
    if root.tag.rpartition("}")[2] != "svg" or "viewBox" not in root.attrib:
        return "the root must be <svg> with a viewBox"
    if {"width", "height"} & set(root.attrib):
        return "no fixed width or height on the root"
    for element in root.iter():
        name = element.tag.rpartition("}")[2].lower()
        if name in ("script", "style", "foreignobject"):
            return f"no <{name}> elements"
        if any(attr.lower().startswith("on") for attr in element.attrib):
            return "no event handler attributes"
    return None


def problems() -> list[str]:
    found = []
    app = json.loads((APP / "app.json").read_text())
    folder = APP.name
    if list(app) != FIELD_ORDER:
        found.append(f"app.json fields should be, in order: {', '.join(FIELD_ORDER)}")
    if re.sub(r"[ \-.:@]", "", app["name"]) != folder:
        found.append("the folder must be the app's name without spaces, dashes, dots, colons or @")
    if app["appid"] != hashlib.sha1(slug(app["name"]).encode()).hexdigest():  # noqa: S324
        found.append("appid must be the SHA-1 of the name's slug")
    if app["tile_background"] not in ("dark", "light"):
        found.append("tile_background must be dark or light")

    icon = APP / app["icon"]
    if icon.suffix not in (".svg", ".png") or not icon.is_file():
        found.append("the icon must be an existing .svg or .png file")
    elif icon.name != f"{slug(app['name'])}{icon.suffix}":
        found.append("the icon's file name must be the slug of the name")
    elif icon.suffix == ".png":
        width, height = struct.unpack(">II", icon.read_bytes()[16:24])
        if not (100 <= width <= 300 and 100 <= height <= 300):
            found.append("a PNG icon must be 100 to 300 pixels on each side")
    elif problem := svg_problem(icon):
        found.append(f"the SVG must be plain: {problem}")

    php = APP / f"{folder}.php"
    source = php.read_text() if php.is_file() else ""
    if f"namespace App\\SupportedApps\\{folder};" not in source:
        found.append(f"{php.name} must declare namespace App\\SupportedApps\\{folder}")
    if f"class {folder} " not in source:
        found.append(f"{php.name} must define class {folder}")
    enhanced = bool(re.search(r"implements\s+\\?App\\EnhancedApps", source))
    blades = all((APP / blade).is_file() for blade in ("config.blade.php", "livestats.blade.php"))
    if app["enhanced"] is not True or not enhanced or not blades:
        found.append("an enhanced app needs enhanced: true, both blades and \\App\\EnhancedApps")
    if any(len(line) > 120 for line in source.splitlines()):
        found.append(f"{php.name} has lines over 120 characters (PSR-12)")
    return found


if __name__ == "__main__":
    if errors := problems():
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
    print(f"{APP.name}: OK")
