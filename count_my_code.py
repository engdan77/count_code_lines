import datetime
import json
import collections
import sys
from json import JSONDecodeError
from typing import Literal, Tuple, Dict, Any, Annotated
from pygount.command import pygount_command
import requests
from tempfile import NamedTemporaryFile, TemporaryDirectory
from pathlib import Path
import typer
from py_markdown_table.markdown_table import markdown_table
from git import Repo
from enum import StrEnum, auto
from rich.logging import RichHandler
import logging
from rich.console import Console
from rich import print_json
from rich.markdown import Markdown


logging.basicConfig(level=logging.INFO, datefmt="[%X]", format="%(message)s", handlers=[RichHandler()])
logger = logging.getLogger(__name__)


EXCLUDE_PATTERN = "...,zope,twisted,garden"

Repository = collections.namedtuple('repo', 'name url year')
CountSummary = dict[Literal['dirs', 'github'], collections.Counter]
ReposSummary = tuple[dict[str | Any, dict]]
Years = Annotated[set, 'years']
SourceLinesPerYear = tuple[Annotated[str, 'source name'], Annotated[collections.defaultdict[str, list], 'source and per year']]

cli_app = typer.Typer()


class OutputFormat(StrEnum):
    MARKDOWN = auto()
    JSON = auto()
    RICH = auto()

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
    prefix = f'''
```mermaid
xychart-beta
      title "{title}"
      x-axis "{x_axis_title}" {json.dumps(list(all_years))}
'''
    data_lines = []
    for source, data_list in per_source.items():
        data_lines.append(f'      bar "{source.split('/').pop()}" {json.dumps(data_list)}')
    return prefix + '\n'.join(data_lines) + '```'


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


def output_as_markdown(summaries: dict[str, dict]) -> str:
    output_markdown = ''

    for source in summaries:
        table_data = []
        source_data = dict(sorted(summaries[source].items(), key=lambda x: x[1]['year']))
        output_markdown += f'### {source.split('/').pop()}\n\n'
        for repo_name, data in source_data.items():
            table_data.append({'repo_name': repo_name, 'year': data['year'], 'lines_of_code': data['totalCodeCount']})
        output_markdown = markdown_table(table_data).get_markdown()

    all_years, data = get_code_per_year_source(summaries)
    output = code_per_year_to_chart(all_years, data)
    output_markdown += output
    return output_markdown


def output_as_json(summaries: dict[str, dict]) -> dict:
    output_json = {}
    for source in summaries:
        source_data = dict(sorted(summaries[source].items(), key=lambda x: x[1]['year']))
        source_name = f'{source.split('/').pop()}'
        for repo in source_data:
            output_json[source] = []
            output_json[source].append({'repo_name': repo, 'year': source_data['year'], 'lines_of_code': source_data['totalCodeCount']})

    all_years, data = get_code_per_year_source(summaries)
    output_json['per_years'] = all_years
    return output_json



@cli_app.command()
def repos_summary(repos: list[str] = typer.Argument(..., help='Either a path or an URL'),
                  sub_folders_as_repos: bool = typer.Option(True, help='Treat sub-folders as repositories'),
                  output_format: OutputFormat = typer.Option(OutputFormat.RICH, help='Output format')) \
        -> tuple[ReposSummary, CountSummary]:

    r = get_summaries(repos, sub_folders_as_repos)
    match output_format:
        case OutputFormat.MARKDOWN:
            print(output_as_markdown(r), file=sys.stdout)
        case OutputFormat.RICH:
            console = Console()
            md = Markdown(output_as_markdown(r))
            console.print(md)
        case OutputFormat.JSON:
            print_json(json.dumps(output_as_json(r)))









if __name__ == "__main__":
    cli_app()
