import datetime
import json
import collections
from json import JSONDecodeError
from typing import Literal, Tuple, Dict, Any
from pygount.command import pygount_command
import requests
from tempfile import NamedTemporaryFile, TemporaryDirectory
from pathlib import Path
import typer
from loguru import logger
from py_markdown_table.markdown_table import markdown_table
from git import Repo

Repository = collections.namedtuple('repo', 'name url year')
CountSummary = dict[Literal['dirs', 'github'], collections.Counter]
ReposSummary = tuple[dict[str | Any, dict]]

cli_app = typer.Typer()


def get_all_github_repos(user='engdan77') -> list[Repository]:
    repos = []
    for r in requests.get(f'https://api.github.com/users/{user}/repos').json():
        year = r['created_at'].split('-').pop(0)
        repos.append(Repository(r['name'], f"{r['html_url']}.git", year))
    return sorted(repos, key=lambda x: x.year)


def get_repo_summary_file(tmp_file: NamedTemporaryFile, repo_folder: Path | str) -> dict:
    """Why: abstract reading the file and also add year"""
    if isinstance(repo_folder, Path):
        f = repo_folder.as_posix()
    else:
        f = repo_folder.url
    pygount_command(['--format', 'json', '--out', tmp_file.name, f])
    try:
        summary = json.loads(open(tmp_file.name).read())['summary']
        summary['year'] = get_repo_create_year(repo_folder)
    except JSONDecodeError:
        logger.warning(f'Unable to find data for {repo_folder}')
        summary = {}
    return summary


def get_repo_create_year(source: str | Repository) -> int:
    with TemporaryDirectory() as tmp_folder:
        if isinstance(source, Repository):
            r = Repo.clone_from(source.url, tmp_folder)
        else:
            r = Repo(source)
        first_commit = next(r.iter_commits())
        year = datetime.datetime.fromtimestamp(first_commit.committed_date).year
        return year


def get_repo_create_year_by_url(url: str) -> int:
    with TemporaryDirectory() as tmp_folder:
        r = Repo.clone_from(url, tmp_folder)
        first_commit = next(r.iter_commits())
        year = datetime.datetime.fromtimestamp(first_commit.committed_date).year
        return year


@cli_app.command()
def repos_summary(repos: list[str] = typer.Argument(..., help='Either a path or an URL'),
                  sub_folders_as_repos: bool = typer.Option(True, help='Treat sub-folders as repositories')) \
        -> tuple[ReposSummary, CountSummary]:

    r = get_summaries(repos, sub_folders_as_repos)
    repo_md = None

    table_data = []
    for source in r:
        source_data = dict(sorted(r[source].items(), key=lambda x: x[1]['year']))
        print(f'*{source.split('/').pop()}*')
        for repo_name, data in source_data.items():
            table_data.append({'repo_name': repo_name.pop(), 'year': data['year'], 'lines_of_code': data['totalCodeCount']})
    markdown = markdown_table(table_data).get_markdown()
    print(markdown)


def get_summaries(sources, parse_sub_folders_as_repos) -> dict[str, dict]:
    summarization = collections.defaultdict(dict)
    with NamedTemporaryFile() as tmp_file:
        logger.info(f'Temp file {tmp_file.name}')
        for source in sources:
            repo_item: Path | str = Path(source)
            if repo_item.is_dir():
                if parse_sub_folders_as_repos:
                    process_sources = repo_item.glob('*/')
                else:
                    process_sources = [repo_item]
            else:
                process_sources = get_all_github_repos(repo_item)

            for process_source in process_sources:
                logger.info(f'Processing {source} / {process_source.name.strip()}')
                summary = get_repo_summary_file(tmp_file, process_source)
                summarization[source][process_source.name] = summary
    return summarization


if __name__ == "__main__":
    cli_app()
