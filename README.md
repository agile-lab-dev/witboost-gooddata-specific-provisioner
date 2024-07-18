<p align="center">
    <a href="https://witboost.com/">
        <img src="docs/img/witboost_logo.svg" alt="witboost" width=600 >
    </a>
</p>

Designed by [Agile Lab](https://www.agilelab.it/), witboost is a versatile platform that addresses various sophisticated data engineering challenges. It enables businesses to discover, enhance, and productize their data, fostering the creation of automated data platforms that adhere to the highest standards of data governance. Want to know more about witboost? Check it out [here](https://www.witboost.com) or [contact us!](https://witboost.com/contact-us)

This repository is part of our [Starter Kit](https://github.com/agile-lab-dev/witboost-starter-kit) meant to showcase witboost's integration capabilities and provide a "batteries-included" product.

# GoodData Specific Provisioner

- [Overview](#overview)
- [Building](#building)
- [Running](#running)
- [OpenTelemetry Setup](gooddata-sp/docs/opentelemetry.md)
- [Deploying](#deploying)
- [API specification](docs/API.md)

## Overview

This project implements a Specific Provisioner for GoodData, using Python & FastAPI.
![image](https://github.com/user-attachments/assets/fbb3c566-0b88-49e1-a7eb-d74fdbb2a3f7)

[GoodData](https://www.gooddata.com/) is an AI-fueled data analytics platform for creating customized data products with advanced interactive analytics capabilities.
GoodData offers great API to automate the full lifecycle of data models and dashboards, also managing multiple environments.

This integration is automating several aspects:
- workspace creation
- data model management
- dashboard creation and deployment
- user profiles setting
- business metadata management

  ![image](https://github.com/user-attachments/assets/53f0cf9a-884a-4ee9-8549-35b2224d6823)



### What's a Specific Provisioner?

A Specific Provisioner is a microservice which is in charge of deploying components that use a specific technology. When the deployment of a Data Product is triggered, the platform generates it descriptor and orchestrates the deployment of every component contained in the Data Product. For every such component the platform knows which Specific Provisioner is responsible for its deployment, and can thus send a provisioning request with the descriptor to it so that the Specific Provisioner can perform whatever operation is required to fulfill this request and report back the outcome to the platform.

You can learn more about how the Specific Provisioners fit in the broader picture [here](https://docs.witboost.agilelab.it/docs/p2_arch/p1_intro/#deploy-flow).



### Software stack

This microservice is written in Python 3.11, using FastAPI for the HTTP layer. Project is built with Poetry and supports packaging as Wheel and Docker image, ideal for Kubernetes deployments (which is the preferred option).

## Building

**Requirements:**

- Python 3.11
- Poetry

**Installing**:

To set up a Python environment we use [Poetry](https://python-poetry.org/docs/):

```
curl -sSL https://install.python-poetry.org | python3 -
```

Once Poetry is installed and in your `$PATH`, you can execute the following:

```
poetry --version
```

If you see something like `Poetry (version x.x.x)`, your install is ready to use!

Install the dependencies defined in `gooddata-sp/pyproject.toml`:
```
cd gooddata-sp
poetry install
```

*Note:* All the following commands are to be run in the Poetry project directory with the virtualenv enabled.

**Type check:** is handled by mypy:

```bash
poetry run mypy gooddata_sp/
```

**Tests:** are handled by pytest:

```bash
poetry run pytest --cov=gooddata_sp/ tests/. --cov-report=xml
```

**Artifacts & Docker image:** the project leverages Poetry for packaging. Build package with:

```
poetry build
```

The Docker image can be built with:

```
docker build .
```

More details can be found [here](gooddata-sp/docs/docker.md).

*Note:* the version for the project is automatically computed using information gathered from Git, using branch name and tags. Unless you are on a release branch `1.2.x` or a tag `v1.2.3` it will end up being `0.0.0`. You can follow this branch/tag convention or update the version computation to match your preferred strategy.

**CI/CD:** the pipeline is based on GitLab CI as that's what we use internally. It's configured by the `.gitlab-ci.yaml` file in the root of the repository. You can use that as a starting point for your customizations.

## Configuration

All configurations are picked up from environment variables. The following table describes the available configurations and whether they are required or optional.

| Environment variable | Required | Example                   | Description                     |
|----------------------|----------|---------------------------|---------------------------------|
| GOODDATA_HOST        | Yes      | "https://www.example.com" | GoodData instance URL           |
| GOODDATA_TOKEN       | Yes      | "some_user_token"         | Token for API calls to GoodData |

## Running

To run the server locally, use:

```bash
cd gooddata_sp
source $(poetry env info --path)/bin/activate # only needed if venv is not already enabled
uvicorn gooddata_sp.main:app --host 127.0.0.1 --port 8091
```

By default, the server binds to port 8091 on localhost. After it's up and running you can make provisioning requests to this address. You can also check the API documentation served [here](http://127.0.0.1:8091/docs).

## Deploying

This microservice is meant to be deployed to a Kubernetes cluster with the included Helm chart and the scripts that can be found in the `helm` subdirectory. You can find more details [here](helm/README.md).

## License

This project is available under the [Apache License, Version 2.0](https://opensource.org/licenses/Apache-2.0); see [LICENSE](LICENSE) for full details.

## About us

<p align="center">
    <a href="https://www.witboost.com">
        <img src="docs/img/witboost_logo.svg" alt="Witboost" width=600>
    </a>
</p>

From Chaos to Control: Data Experience on Guardrails
Craft your own standards and automate your data practice

[Contact us](https://witboost.com/contact-us) or follow us on:
- [LinkedIn](https://www.linkedin.com/showcase/witboost/)
- [Instagram](https://www.instagram.com/agilelab_official/)
- [YouTube](https://www.youtube.com/channel/UCTWdhr7_4JmZIpZFhMdLzAA)
- [Twitter](https://twitter.com/agile__lab)
