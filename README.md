# wattpad-archiver
A script to download and archive your Wattpad Bookshelf in EPUB format

## Usage
You can run the script with python 3 if you have all the dependencies installed

```
$ python archiver.py
```

Note that you will have to provide at least an username and a token (see below)

### Installing with poetry
If you want isolation or don't want to install all the dependencies by hand, you can use poetry to create a virtualenv with everything installed

```
$ poetry install
$ poetry shell

$ USERNAME=<user>
$ TOKEN=00000000

$ python archiver.py
```

### Running with docker
If you want you can also use the Docker image available on Docker Hub

```
docker run -it --rm -v ./output:/output -e WATTPAD_USERNAME=<user> -e TOKEN=00000000 wattpad-archiver:latest
```

More information on environment arguments below

## Script arguments
The script takes arguments from environment variables, below is a list of which are available

| Variable Name | Usage |
| --- | --- |
| `WATTPAD_USERNAME` 	| Username of your wattpad profile |
| `TOKEN` 				| Wattpad profile token, see [how to get it](#getting-a-token) |
| `AGENT` 				| HTTP User Agent the script should use when making requests, default: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/105.0.0.0 Safari/537.36` |
| `MULTITHREAD` | If set to `true` starts a separate thread for every story to download instead of working sequentially, it is recommended to fine-tune the `RATELIMIT` option when enabling multithreading to avoid being tempbanned, default: `false` |
| `RATELIMIT` | Sets the max number of requests made in one second, default is `20` which seems a pretty conservative estimate to not trigger any protection |
| `MAX_RETRIES` | Sets the maximum number of retries for a request before terminating the whole process, default: `30` |
| `OUTPUT` | Sets the output directory, which will be created if non existent, default: `./output` |
| `MAX_STORIES` | Sets the maximum number of stories to download, default: `-1` (no limit) |
| `DEBUG` | If set to `true` enables debug logging of all HTTP requests, default: `false` |

## Getting a token
Wattpad's api is private, as such the api token is not available to the public. However, it is possible to get it by using the browser's developer tools by reading the stored cookies when logged in.

To do so, make sure you're logged in and go to a random page on wattpad(the homepage is fine), then open the developer tools and go to the `Application` tab, then `Cookies` and look for the `token` cookie. Copy the value and use it as the `TOKEN` environment variable.
