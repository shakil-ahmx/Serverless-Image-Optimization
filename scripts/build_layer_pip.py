#!/usr/bin/env python3
"""Build the Pillow Lambda layer WITHOUT Docker (works on Windows/Mac/Linux).
Downloads Linux x86_64 wheels so the layer runs on AWS Lambda (python3.12)."""
import os, shutil, subprocess, sys, zipfile

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tf_dir = os.path.join(root, "terraform")
build = os.path.join(tf_dir, "_layer_build")
site = os.path.join(build, "python", "lib", "python3.12", "site-packages")
out = os.path.join(tf_dir, "pillow_layer.zip")

shutil.rmtree(build, ignore_errors=True)
os.makedirs(site)
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--quiet", "Pillow==10.4.0",
    "--platform", "manylinux2014_x86_64", "--platform", "manylinux_2_28_x86_64",
    "--implementation", "cp", "--python-version", "3.12",
    "--only-binary=:all:", "--target", site,
])
if os.path.exists(out):
    os.remove(out)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for folder, _, files in os.walk(os.path.join(build, "python")):
        for f in files:
            full = os.path.join(folder, f)
            z.write(full, os.path.relpath(full, build))
shutil.rmtree(build, ignore_errors=True)
print("Layer built:", out)
