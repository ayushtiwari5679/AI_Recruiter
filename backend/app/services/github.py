import os
from urllib.parse import urlparse
import httpx


def _username(value: str) -> str:
    value = (value or '').strip()
    if not value:
        return ''
    if 'github.com' not in value and '/' not in value:
        return value.lstrip('@')
    try:
        path = urlparse(value if '://' in value else 'https://' + value).path.strip('/')
        return path.split('/')[0] if path else ''
    except Exception:
        return ''


async def analyze_github(url: str):
    username = _username(url)
    if not username:
        return {"score": 0, "repositories": 0, "languages": [], "stars": 0, "error": "Missing GitHub profile"}

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "myNachiketa-candidate-screening",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=headers) as client:
        profile = await client.get(f"https://api.github.com/users/{username}")
        if profile.status_code == 404:
            return {"score": 0, "repositories": 0, "languages": [], "stars": 0, "error": f"GitHub user '{username}' not found"}
        if profile.status_code != 200:
            remaining = profile.headers.get("x-ratelimit-remaining")
            return {"score": 0, "repositories": 0, "languages": [], "stars": 0,
                    "error": f"GitHub API returned {profile.status_code}. Rate limit remaining: {remaining}"}

        r = await client.get(
            f"https://api.github.com/users/{username}/repos",
            params={"per_page": 100, "sort": "updated", "type": "owner"},
        )
        if r.status_code != 200:
            return {"score": 0, "repositories": 0, "languages": [], "stars": 0,
                    "error": f"Could not read repositories (GitHub {r.status_code})"}

        repos = [x for x in r.json() if not x.get("fork")]
        languages = sorted({x.get("language") for x in repos if x.get("language")})
        stars = sum(int(x.get("stargazers_count", 0) or 0) for x in repos)
        documented = sum(bool((x.get("description") or '').strip()) for x in repos)
        recent = sum(1 for x in repos if x.get("pushed_at"))
        score = min(100, len(repos) * 4 + min(stars, 25) + documented * 2 + len(languages) * 3 + min(recent, 10))

        top_repositories = [
            {"name": x.get("name"), "language": x.get("language"), "stars": x.get("stargazers_count", 0),
             "url": x.get("html_url"), "description": x.get("description")}
            for x in sorted(repos, key=lambda z: (z.get("stargazers_count", 0), z.get("updated_at", "")), reverse=True)[:5]
        ]
        return {
            "username": username,
            "profile": f"https://github.com/{username}",
            "score": round(score, 2),
            "repositories": len(repos),
            "languages": languages,
            "stars": stars,
            "documented_repositories": documented,
            "top_repositories": top_repositories,
        }
