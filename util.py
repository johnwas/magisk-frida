import re
import requests
import subprocess


# gets phantom-frida release matching a specific frida version
# tag format: v{frida_version}-{date}, e.g. v17.7.2-20241215
# returns: {tag, name, port, version, assets: {"arm64": url, "arm": url, ...}}
def get_phantom_frida_release(repo: str, frida_version: str) -> dict:
    releases_url = f"https://api.github.com/repos/{repo}/releases"
    r = requests.get(releases_url)
    r.raise_for_status()

    matching = [rel for rel in r.json() if rel["tag_name"].startswith(f"v{frida_version}-")]
    if not matching:
        raise ValueError(f"No phantom-frida release found for frida {frida_version} in {repo}")
    release = matching[0]

    info_asset = next(
        (a for a in release["assets"] if a["name"] == "build-info.json"),
        None
    )
    if info_asset is None:
        raise ValueError(f"build-info.json not found in release {release['tag_name']}")
    build_info = requests.get(info_asset["browser_download_url"]).json()

    # key: arch suffix after "android-", e.g. "arm64", "arm"
    assets = {
        a["name"].split("-android-")[1].replace(".gz", ""): a["browser_download_url"]
        for a in release["assets"]
        if a["name"].endswith(".gz") and "-server-" in a["name"]
    }

    print(f"Found phantom-frida release: {release['tag_name']} (name={build_info['name']}, archs={list(assets.keys())})")
    return {
        "tag": release["tag_name"],
        "name": build_info["name"],
        "port": build_info["port"],
        "version": build_info["version"],
        "assets": assets,
    }


# 12.7.5-2, 12.7.5-3, ... -> 12.7.5
def strip_revision(tag) -> str:
    return tag.split('-', 1)[0]


# gets last tag of GitHub project
def get_last_github_tag(project_name) -> str:
    releases_url = f"https://api.github.com/repos/{project_name}/releases/latest"
    r = requests.get(releases_url)
    r.raise_for_status()
    releases = r.json()
    # TODO: don't assume order
    last_release = releases["tag_name"]
    return last_release


# gets last tag of frida
def get_last_frida_tag() -> str:
    last_frida_tag = get_last_github_tag('frida/frida')
    print(f"Last frida tag: {last_frida_tag}")
    return last_frida_tag


# gets last tag of whole project
def get_last_project_tag() -> str:
    last_tag = get_last_tag([])
    print(f"Last project tag: {last_tag}")
    return last_tag


# properly sort tags (e.g. 1.11 > 1.9)
def sort_tags(tags: [str]) -> [str]:
    tags = tags.copy()
    s: str
    tags.sort(key=lambda s: list(map(int, re.split(r"[\.-]", s))))
    return tags


# gets last tag from filter
def get_last_tag(filter_args: [str]) -> str:
    tags = exec_git_command(["tag", "-l"] + filter_args).splitlines()
    last_tag = "" if len(tags) < 1 else sort_tags(tags)[-1]
    return last_tag


# executes a git command
def exec_git_command(command_with_args: [str]) -> str:
    result = subprocess.run(["git"] + command_with_args,
                            capture_output=True).stdout
    return result.decode()


# gets next tag in the form 12.7.5-1, 12.7.5-2...
def get_next_revision(current_tag: str) -> str:
    i = 1
    while True:
        new_tag = f"{current_tag}-{i}"
        if get_last_tag([new_tag]) == '':
            break
        i += 1
    return new_tag
