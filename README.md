
# Library.canonical.com

Library.canonical.com is a webpage designed to serve as a centralized source of truth for all corporate information within Canonical. It consolidates various forms of content stored in Google Drive and dynamically builds the site's structure based on the file structure in Google Drive. This project was initiated to address the challenge of scattered information across multiple sites, making it difficult to find the required information efficiently.


## Bugs, issues and contributions

If you have found a bug on the site or have an idea for a new feature, feel free to create a [new issue](https://github.com/canonical/library.canonical.com/issues/new), or suggest a fix by creating a [pull request](https://github.com/canonical/library.canonical.com/pulls). You can also find a link to create issues in the footer of every page of the site itself.

## Local development

The simplest way to run the site locally is using the [`dotrun`](https://github.com/canonical-web-and-design/dotrun/) snap. Please use the installation scripts [mentioned in the README](https://github.com/canonical-web-and-design/dotrun/blob/main/README.md#installation) to install `dotrun`.

You will need to add the appropriate variables to `.env.local`, these can be found in LastPass by searching for library.canonical.com.

Lastly, you will need to have a local memcached server running. You can install it with `apt-get install memcached` and start it with `sudo service start memcached`. It needs to be running on 'localhost:11211', the default settings. You can check this by running `telnet localhost 11211`. If you can't find the server, configure it following the [official guide](https://github.com/memcached/memcached/wiki/ConfiguringServer). 

Once it's installed, run the project with:

```bash
dotrun
```

Once the server has started, you can visit <http://0.0.0.0:8051> in your browser.

With ♥ from Canonical
