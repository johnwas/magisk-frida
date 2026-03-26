#!/user/bin/env python3
import gzip
import logging
import lzma
import os
from pathlib import Path
import shutil
import threading
import zipfile
import concurrent.futures
import json
import re

import requests

PATH_BASE = Path(__file__).parent.resolve()
PATH_BASE_MODULE: Path = PATH_BASE.joinpath("base")
PATH_BUILD: Path = PATH_BASE.joinpath("build")
PATH_BUILD_TMP: Path = PATH_BUILD.joinpath("tmp")
PATH_DOWNLOADS: Path = PATH_BASE.joinpath("downloads")

logger = logging.getLogger()
syslog = logging.StreamHandler()
formatter = logging.Formatter("%(threadName)s : %(message)s")
syslog.setFormatter(formatter)
logger.setLevel(logging.INFO)
logger.addHandler(syslog)


def download_file(url: str, path: Path):
    file_name = url[url.rfind("/") + 1 :]
    logger.info(f"Downloading '{file_name}' to '{path}'")

    if path.exists():
        return

    r = requests.get(url, allow_redirects=True)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

    logger.info("Done")


def extract_file(archive_path: Path, dest_path: Path):
    logger.info(f"Extracting '{archive_path.name}' to '{dest_path.name}'")

    with lzma.open(archive_path) as f:
        file_content = f.read()
        path = dest_path.parent

        path.mkdir(parents=True, exist_ok=True)

        with open(dest_path, "wb") as out:
            out.write(file_content)


def extract_gz_file(archive_path: Path, dest_path: Path):
    logger.info(f"Extracting '{archive_path.name}' to '{dest_path.name}'")

    with gzip.open(archive_path) as f:
        file_content = f.read()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as out:
            out.write(file_content)


def generate_version_code(project_tag: str) -> int:
    parts = re.split("[-.]", project_tag)
    version_code = "".join(f"{int(part):02d}" for part in parts)
    return int(version_code)


def create_module_prop(path: Path, project_tag: str):
    module_prop = f"""id=magisk-frida
name=MagiskFrida
version={project_tag}
versionCode={generate_version_code(project_tag)}
author=ViRb3 & enovella
updateJson=https://github.com/ViRb3/magisk-frida/releases/latest/download/updater.json
description=Run frida-server on boot"""

    with open(path.joinpath("module.prop"), "w", newline="\n") as f:
        f.write(module_prop)


def create_module(project_tag: str):
    logger.info("Creating module")

    if PATH_BUILD_TMP.exists():
        shutil.rmtree(PATH_BUILD_TMP)

    shutil.copytree(PATH_BASE_MODULE, PATH_BUILD_TMP)
    create_module_prop(PATH_BUILD_TMP, project_tag)


# magisk-frida arch names that have a phantom-frida counterpart
# x86 / x86_64 are not built by phantom-frida
_PHANTOM_ARCH_MAP = {"arm64": "arm64", "arm": "arm"}


def fill_module(arch: str, frida_tag: str, phantom_release: dict | None = None):
    threading.current_thread().setName(arch)
    logger.info(f"Filling module for arch '{arch}'")

    files_dir = PATH_BUILD_TMP.joinpath("files")
    files_dir.mkdir(exist_ok=True)

    if phantom_release is not None:
        phantom_arch = _PHANTOM_ARCH_MAP.get(arch)
        if phantom_arch is None or phantom_arch not in phantom_release["assets"]:
            logger.info(f"No phantom-frida build for arch '{arch}', skipping")
            return

        name = phantom_release["name"]
        version = phantom_release["version"]
        filename = f"{name}-server-{version}-android-{phantom_arch}.gz"
        local_path = PATH_DOWNLOADS.joinpath(filename)

        download_file(phantom_release["assets"][phantom_arch], local_path)
        server_name = f"{name}-server"
        extract_gz_file(local_path, files_dir.joinpath(f"{server_name}-{arch}"))
        (files_dir / f"server-name-{arch}").write_text(server_name)
    else:
        frida_download_url = (
            f"https://github.com/frida/frida/releases/download/{frida_tag}/"
        )
        frida_server = f"frida-server-{frida_tag}-android-{arch}.xz"
        frida_server_path = PATH_DOWNLOADS.joinpath(frida_server)

        download_file(frida_download_url + frida_server, frida_server_path)
        server_name = "frida-server"
        extract_file(frida_server_path, files_dir.joinpath(f"{server_name}-{arch}"))
        (files_dir / f"server-name-{arch}").write_text(server_name)


def create_updater_json(project_tag: str):
    logger.info("Creating updater.json")

    updater = {
        "version": project_tag,
        "versionCode": generate_version_code(project_tag),
        "zipUrl": f"https://github.com/ViRb3/magisk-frida/releases/download/{project_tag}/MagiskFrida-{project_tag}.zip",
        "changelog": "https://raw.githubusercontent.com/ViRb3/magisk-frida/master/CHANGELOG.md",
    }

    with open(PATH_BUILD.joinpath("updater.json"), "w", newline="\n") as f:
        f.write(json.dumps(updater, indent=4))


def package_module(project_tag: str):
    logger.info("Packaging module")

    module_zip = PATH_BUILD.joinpath(f"MagiskFrida-{project_tag}.zip")

    with zipfile.ZipFile(module_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(PATH_BUILD_TMP):
            for file_name in files:
                if file_name == "placeholder" or file_name == ".gitkeep":
                    continue
                zf.write(
                    Path(root).joinpath(file_name),
                    arcname=Path(root).relative_to(PATH_BUILD_TMP).joinpath(file_name),
                )

    shutil.rmtree(PATH_BUILD_TMP)


def do_build(frida_tag: str, project_tag: str, phantom_release: dict | None = None):
    PATH_DOWNLOADS.mkdir(parents=True, exist_ok=True)
    PATH_BUILD.mkdir(parents=True, exist_ok=True)

    create_module(project_tag)

    archs = ["arm", "arm64", "x86", "x86_64"]
    executor = concurrent.futures.ProcessPoolExecutor()
    futures = [
        executor.submit(fill_module, arch, frida_tag, phantom_release) for arch in archs
    ]
    for future in concurrent.futures.as_completed(futures):
        if future.exception() is not None:
            raise future.exception()

    package_module(project_tag)
    create_updater_json(project_tag)

    logger.info("Done")
