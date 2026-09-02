"""Prepare GTA IV's shader folders so an old ENB preset sees stock shaders.

    python make_vanilla_package.py --game "<...>/Grand Theft Auto IV/GTAIV" --stage-extras
    python make_vanilla_package.py --game "<...>" --out <dir> [--pure] [--install]

Why this exists
---------------
ENBSeries recognises a game shader by hashing its compiled bytecode and swaps in
the assembly from its ``shaderinput/psh<HASH>.txt``. The FusionFix shader package
replaces all 102 stock ``.fxc`` containers with rewritten ones -- every single
shader gets a different hash -- so an old preset matches nothing and its effects
are applied on top of a scene the preset never got to modify.

Removing ``update/common/shaders`` outright is not a fix either: FusionFix's own
content packages reference ``gta_trees_extended``, which only exists in that
package, and the game throws a resource error before the main menu without it.

Three ways to give the preset what it needs
-------------------------------------------
All of them work through the same mechanism: with ``[ENBCompatibility]
FusionShaderPackage = 0`` the .asi points the game's shader-variant lookups at
``StockShaderFolder`` (default ``win32_30_nv8``) instead of ``win32_30``, and
anything not present in that folder's update overlay falls through to the stock
copy in ``common/shaders``. The overlay works per file, so what is placed there
decides, container by container, which side wins.

**``--selective`` -- keep most of FusionFix.** Stages the FusionFix version of
every container *except* the ones holding a shader an ENB preset replaces. Those
fall through to stock, so the preset's hashes have something to match, while
FusionFix keeps the rest. Measured against CE 1.2.0.59, the default set gives up
9 containers holding 191 of 1739 FusionFix shaders -- **89% retained**. Keep
``ShaderConstantInjection = 1`` in this mode: most of the FusionFix shaders are
still there and still read c208..c223 / c227..c237.

**``--stage-extras`` -- all stock.** Copies only ``gta_trees_extended.fxc``, the
one shader FusionFix genuinely adds rather than replaces and which its content
packages reference. Everything else falls through, so the game runs entirely on
stock shaders. One file.

**``--out``/``--install`` -- rebuild the package in place.** Replaces
``update/common/shaders`` itself with stock bytecode plus the FusionFix-only
additions. Heavier and destructive-ish (the old folder is renamed aside), but it
targets ``win32_30`` specifically, which is worth trying if the preset turns out
to have been built against that variant. ``--pure`` drops the FusionFix addition
too, in which case the content packages referencing it must also be removed or
the game will not start.

Measured on CE 1.2.0.59: ``win32_30`` and ``win32_30_nv8`` are byte-identical
for 1688 of their 1689 shaders, so in practice the routes present almost exactly
the same bytecode.

Container granularity is the floor. Shaders inside a ``.fxc`` cannot be swapped
individually without rebuilding the container, so a container is given up whole
even when only one shader in it is wanted -- which is why
``deferred_lighting.fxc`` (62 shaders, two of them targeted) is left out of the
default selective set.

Nothing is written into the game folder without ``--selective``,
``--stage-extras`` or ``--install``.
"""

import argparse
import os
import shutil
import sys
import time

FUSION_ONLY = {
    "win32_30/gta_trees_extended.fxc",
    "db/gta_trees_extended.sps",
    "dcl/gta_trees_extended.dcl",
}

VARIANTS = ("win32_30", "win32_30_low_ati", "win32_30_nv6",
            "win32_30_nv7", "win32_30_nv8", "win32_30_atidx10")

# Containers holding a shader that ENBSeries 0.163 or iCEnhancer 4.0 replaces,
# from research/shader-map.json. Grouped by what giving one up actually costs.
#
# A container is the finest granularity available: the update tree overlays per
# file, and the shaders inside a .fxc cannot be swapped individually without
# rebuilding it.
ENB_TARGETS = {
    # Free in ENB mode -- ENB owns the post-process stage regardless.
    "rage_postfx.fxc": "post-process; ENB replaces it via enbeffect.fx anyway",

    # Cheap and confidently identified: each target is unique to its container
    # and matches stock CE at similarity 1.000 (0.817 for grass).
    "gta_terrain_va_2lyr.fxc": "psh0CBF49C5, two-layer terrain",
    "gta_terrain_va_3lyr.fxc": "psh405ABC1B, three-layer terrain",
    "gta_terrain_va_4lyr.fxc": "psh841FD9AE, four-layer terrain",
    "gta_grass.fxc": "psh71CC11CF, grass",

    # psh2DF967C6 is one bytecode present in all three of these containers, so
    # they stand or fall together.
    "gta_default.fxc": "psh2DF967C6, stipple-faded surface (also in the next two)",
    "gta_cutout_fence.fxc": "psh2DF967C6, same bytecode as gta_default",
    "gta_wire.fxc": "psh2DF967C6, same bytecode as gta_default",

    # Expensive: 62 shaders, and the two targets in it are only the vegetation
    # wind-sway vertex shaders. Skip unless the preset's tree animation matters.
    "deferred_lighting.fxc": "vsh54F25463 + vshC35A5E05, vegetation wind sway",
}


def rel_files(root):
    out = set()
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            out.add(os.path.relpath(full, root).replace("\\", "/"))
    return out


def stage_extras(current, variant):
    """Copy the FusionFix-only shader into one variant folder's update overlay.

    The update tree overlays the base game per file, not per directory, so a
    folder holding nothing but this one shader leaves every other lookup falling
    through to the stock ``common/shaders`` copy -- which is the whole point.
    """
    src_dir = os.path.join(current, "win32_30")
    dst_dir = os.path.join(current, variant)
    name = "gta_trees_extended.fxc"
    src = os.path.join(src_dir, name)

    if not os.path.isfile(src):
        print("not found: %s" % src)
        print("Nothing to stage -- is the FusionFix shader package installed?")
        return 1

    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, name)
    shutil.copy2(src, dst)
    print("staged %s" % dst)

    # db/ and dcl/ are not variant-specific, so they are already reachable.
    for rel in ("db/gta_trees_extended.sps", "dcl/gta_trees_extended.dcl"):
        path = os.path.join(current, rel.replace("/", os.sep))
        print("  %-44s %s" % (rel, "present" if os.path.isfile(path) else "MISSING"))

    print("\nSet these in [ENBCompatibility]:")
    print("  FusionShaderPackage = 0")
    print("  StockShaderFolder   = %s" % variant)
    print("\nTo undo, delete %s" % dst_dir)
    return 0


def stage_selective(current, variant, keep_stock):
    """Stage a package that is FusionFix everywhere except ``keep_stock``.

    Builds an overlay under the chosen variant folder holding the FusionFix
    version of every container *except* the ones an ENB preset needs to
    recognise. Those are simply absent, so the game falls through to the stock
    copy in ``common/shaders`` and the preset's hashes have something to match.

    Nothing under ``win32_30`` is touched, so the original FusionFix package
    stays intact and undoing this is deleting one folder.
    """
    src = os.path.join(current, "win32_30")
    dst = os.path.join(current, variant)
    if not os.path.isdir(src):
        print("not found: %s" % src)
        print("Nothing to stage -- is the FusionFix shader package installed?")
        return 1

    unknown = sorted(set(keep_stock) - set(os.listdir(src)))
    if unknown:
        print("not in the FusionFix package: %s" % ", ".join(unknown))
        return 1

    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)

    copied = skipped = 0
    for name in sorted(os.listdir(src)):
        if not name.lower().endswith(".fxc"):
            continue
        if name in keep_stock:
            skipped += 1
            continue
        shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
        copied += 1

    print("staged %s" % dst)
    print("  %d containers kept from FusionFix" % copied)
    print("  %d left to fall through to the stock game:" % skipped)
    for name in sorted(keep_stock):
        print("      %-30s %s" % (name, ENB_TARGETS.get(name, "")))

    print("\nSet these in [ENBCompatibility]:")
    print("  FusionShaderPackage     = 0")
    print("  StockShaderFolder       = %s" % variant)
    print("  ShaderConstantInjection = 1   ; the FusionFix shaders that remain need it")
    print("\nTo undo, delete %s" % dst)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True,
                    help="the GTAIV folder holding GTAIV.exe, common/ and update/")
    ap.add_argument("--stage-extras", action="store_true",
                    help="copy gta_trees_extended.fxc into the update overlay for "
                         "--variant, for use with FusionShaderPackage = 0")
    ap.add_argument("--selective", action="store_true",
                    help="stage a package that keeps FusionFix's shaders except in the "
                         "containers an ENB preset needs to recognise")
    ap.add_argument("--keep-stock", metavar="CONTAINER", nargs="*", default=None,
                    help="containers to leave to the stock game (default: all of "
                         "ENB_TARGETS except deferred_lighting.fxc). "
                         "Pass 'list' to print the known targets and exit")
    ap.add_argument("--variant", default="win32_30_nv8", choices=VARIANTS,
                    help="shader-variant folder to stage into (default: %(default)s)")
    ap.add_argument("--out", help="staging directory to build a full package into")
    ap.add_argument("--pure", action="store_true",
                    help="stock shaders only; drop the FusionFix-only additions")
    ap.add_argument("--install", action="store_true",
                    help="also move the built package into <game>/update/common/shaders")
    args = ap.parse_args(argv)

    game = os.path.abspath(args.game)
    stock = os.path.join(game, "common", "shaders")
    current = os.path.join(game, "update", "common", "shaders")

    if not os.path.isdir(stock):
        print("not found: %s" % stock)
        return 1

    if args.keep_stock == ["list"]:
        print("Containers holding a shader an ENB preset replaces:\n")
        for name, why in sorted(ENB_TARGETS.items()):
            print("  %-30s %s" % (name, why))
        return 0

    if (args.stage_extras or args.selective) and args.variant == "win32_30":
        print("--variant win32_30 is the folder the FusionFix package already"
              " overlays, so staging into it changes nothing. Pick another.")
        return 1

    if args.selective:
        keep = set(args.keep_stock) if args.keep_stock is not None \
            else set(ENB_TARGETS) - {"deferred_lighting.fxc"}
        return stage_selective(current, args.variant, keep)

    if args.stage_extras:
        return stage_extras(current, args.variant)

    if not args.out:
        ap.error("one of --stage-extras, --selective or --out is required")

    out = os.path.abspath(args.out)
    if os.path.isdir(out):
        shutil.rmtree(out)

    # Only win32_30 is copied from the stock tree: FusionFix redirects every
    # shader-variant path to that one folder, so the nv6/nv7/nv8/atidx10 sets
    # are never consulted once the .asi is loaded.
    src_win32 = os.path.join(stock, "win32_30")
    dst_win32 = os.path.join(out, "win32_30")
    os.makedirs(dst_win32)
    copied = 0
    for name in sorted(os.listdir(src_win32)):
        if not name.lower().endswith(".fxc"):
            continue
        shutil.copy2(os.path.join(src_win32, name), os.path.join(dst_win32, name))
        copied += 1

    kept = []
    if not args.pure:
        if not os.path.isdir(current):
            print("warning: %s does not exist, so there are no FusionFix-only shaders to keep"
                  % current)
        else:
            for rel in sorted(FUSION_ONLY):
                src = os.path.join(current, rel.replace("/", os.sep))
                if not os.path.isfile(src):
                    print("warning: missing %s -- FusionTrees content will not load" % rel)
                    continue
                dst = os.path.join(out, rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                kept.append(rel)

    print("staged %s" % out)
    print("  %d stock .fxc containers from common/shaders/win32_30" % copied)
    print("  %d FusionFix-only files kept: %s" % (len(kept), ", ".join(kept) or "none"))

    if os.path.isdir(current):
        before, after = rel_files(current), rel_files(out)
        gone = sorted(before - after)
        if gone:
            print("  %d file(s) present now but not in the new package" % len(gone))
            for name in gone[:10]:
                print("    %s" % name)
            if len(gone) > 10:
                print("    ... and %d more" % (len(gone) - 10))

    if not args.install:
        print("\nnot installed. Re-run with --install, or copy the folder yourself to:")
        print("  %s" % current)
        return 0

    if os.path.isdir(current):
        backup = current + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        os.rename(current, backup)
        print("\nexisting package moved to %s" % backup)
    os.makedirs(os.path.dirname(current), exist_ok=True)
    shutil.copytree(out, current)
    print("installed to %s" % current)
    print("\nSet FusionShaderPackage=0 in [ENBCompatibility] to match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
