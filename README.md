# Count Code Lines



## Background

It began while looking in the rear mirror to get an idea of how much code one may have written the past years and the distribution between work-related and personal projects. 

I wished this tool to be focused on presenting such visually in my terminal with the years and line of codes in the focus.

At the same time also looking into using Github Actions to automatically update my personal profile at Github to reflect the true (as of today) projects developed so the tool may as well support return the aggregated results as JSON or a Python dictionary to be used by this scheduled action.



## Screenshots

![image-20241010152842601](https://raw.githubusercontent.com/engdan77/project_images/master/uPic/image-20241010152842601.png)



## Installation

```shell
# Install UV as package manager if not already there to support lock file
$ curl -LsSf https://astral.sh/uv/0.4.18/install.sh | sh

# Install the tool as tool in your OS (installs all fixed requirements)
$ uv tool install https://github.com/engdan77/count_code_lines.git
```





## How to use

### Get help

```shell
$ count-code-lines --help
```

### Get metrics in a rich format

E.g., for a specific path and the engdan77 source at Github

```shell
$ count-code-line engdan77 /path/to/local/repos
```

### Get metrics as JSON

```shell
count-code-line --output-format json /path/to/local/repos
```



