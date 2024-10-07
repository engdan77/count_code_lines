import datetime
import json
import collections
from json import JSONDecodeError
from typing import Literal, Tuple, Dict, Any, Annotated
from pygount.command import pygount_command
import requests
from tempfile import NamedTemporaryFile, TemporaryDirectory
from pathlib import Path
import typer
from loguru import logger
from py_markdown_table.markdown_table import markdown_table
from git import Repo


EXCLUDE_PATTERN = "...,zope,twisted,garden"

Repository = collections.namedtuple('repo', 'name url year')
CountSummary = dict[Literal['dirs', 'github'], collections.Counter]
ReposSummary = tuple[dict[str | Any, dict]]
Years = Annotated[set, 'years']
SourceLinesPerYear = tuple[Annotated[str, 'source name'], Annotated[collections.defaultdict[str, list], 'source and per year']]

cli_app = typer.Typer()


def get_code_per_year_source(summary: dict) -> tuple[Years, SourceLinesPerYear]:
    all_years = set()
    for source, repos in summary.items():
        for repo, data in repos.items():
            all_years.add(data['year'])
    source_lines_per_year = collections.defaultdict(list)
    for source, repos in summary.items():
        c = collections.Counter()
        for repo, data in repos.items():
            c[data['year']] += data['totalCodeCount']
        for year, count in c.items():
            source_lines_per_year[source].append(count)
    return all_years, source_lines_per_year


def code_per_year_to_chart(all_years: Years, per_source: SourceLinesPerYear,
                           title:str='Line of codes per source',
                           x_axis_title: str='Year') -> str:
    prefix = f'''xychart-beta
      title "{title}"
      x-axis "{x_axis_title}" {json.dumps(list(all_years))}
'''
    data_lines = []
    for source, data_list in per_source.items():
        data_lines.append(f'      bar "{source.split('/').pop()}" {json.dumps(data_list)}')
    return prefix + '\n'.join(data_lines)


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
    args = ['--folders-to-skip', EXCLUDE_PATTERN] if EXCLUDE_PATTERN else []
    args.extend(['--format', 'json', '--out', tmp_file.name, f])
    pygount_command(args)
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


@cli_app.command()
def repos_summary(repos: list[str] = typer.Argument(..., help='Either a path or an URL'),
                  sub_folders_as_repos: bool = typer.Option(True, help='Treat sub-folders as repositories')) \
        -> tuple[ReposSummary, CountSummary]:
    r = get_summaries(repos, sub_folders_as_repos)

    for source in r:
        table_data = []
        source_data = dict(sorted(r[source].items(), key=lambda x: x[1]['year']))
        print(f'*{source.split('/').pop()}*')
        for repo_name, data in source_data.items():
            table_data.append({'repo_name': repo_name, 'year': data['year'], 'lines_of_code': data['totalCodeCount']})
        markdown = markdown_table(table_data).get_markdown()
        print(markdown)

    all_years, data = get_code_per_year_source(r)
    output = code_per_year_to_chart(all_years, data)
    print(output)



if __name__ == "__main__":
    cli_app()
