"""Web links to commits, built from the git remote URL that Ascrum sends with each push."""

import re

_REMOTE = re.compile(r"^(?:[a-z+]+://)?(?:[^@/]+@)?([^/:]+)(?::\d+)?[/:](.+?)(?:\.git)?/?$", re.IGNORECASE)


def commit_url(remote_url: str | None, sha: str) -> str | None:
    """git@gitlab.host:group/repo.git or https://gitlab.host/group/repo.git -> https://gitlab.host/group/repo/-/commit/<sha>.

    None for local paths (C:/repos/x, /home/me/x.git), which have no web page.
    """
    remote = (remote_url or "").strip()
    match = _REMOTE.match(remote)
    if not match or "." not in match[1]:
        return None
    host, path = match[1], match[2]
    web = f"{'http' if remote.lower().startswith('http:') else 'https'}://{host}/{path}"
    if host.endswith("github.com") or "azure.com" in host or host.endswith("visualstudio.com"):
        return f"{web}/commit/{sha}"
    if host.endswith("bitbucket.org"):
        return f"{web}/commits/{sha}"
    return f"{web}/-/commit/{sha}"  # GitLab, including self-hosted
