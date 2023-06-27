# ST4SD Datastore

The ST4SD Datastore contains micro-services for:

1. recording metadata about steps of virtual experiment instances
2. support the retrieval of metadata, and files, associated with virtual experiment instances

There are 3 microservices and a daemon:

1. `mongo_proxy.py`: A rest-api for querying the database backend (e.g. MongoDB). It comes withlight logic for populating MongoDB documents with interfaces (https://st4sd.github.io/overview/using-a-virtual-experiment-interface).
2. `cluster_gateway.py`: REST-API to serve files associated with virtual experiment instances.
3. `gateway_registry.py`: REST-API that maintains a mapping of 
4. `reporter.py`: A daemon that asynchronously pushes data from a virtual experiment run into a database backend (e.g MongoDB).

## Quick links

- [Getting started](#getting-started)
- [Development](#development)
- [Help and Support](#help-and-support)
- [Contributing](#contributing)
- [License](#license)

## Getting started

### Requirements

#### Python

Running and developing this project requires a recent Python version, it is suggested to use Python 3.7 or above. You can find instructions on how to install Python on the [official website](https://www.python.org/downloads/).

## Development

Coming soon.

### Installing dependencies

Install the dependencies for this project with:

```bash
pip install -r requirements.txt
```

### Developing locally

Coming soon.

### Lint and fix files

Coming soon.

## Help and Support

Please feel free to reach out to one of the maintainers listed in the [MAINTAINERS.md](MAINTAINERS.md) page.

## Contributing 

We always welcome external contributions. Please see our [guidance](CONTRIBUTING.md) for details on how to do so.

## References

If you use ST4SD in your projects, please consider citing the following:

```bibtex
@software{st4sd_2022,
author = {Johnston, Michael A. and Vassiliadis, Vassilis and Pomponio, Alessandro and Pyzer-Knapp, Edward},
license = {Apache-2.0},
month = {12},
title = {{Simulation Toolkit for Scientific Discovery}},
url = {https://github.com/st4sd/st4sd-runtime-core},
year = {2022}
}
```

## License

This project is licensed under the Apache 2.0 license. Please [see details here](LICENSE.md).
